// FileName: consoleWork.ts

import { RunSource } from "../../shared/run";
import { getErrorMessage } from "../../shared/error";
import {
  ensureBoolean,
  ensureCustomProjectArgs,
  ensureLogLevel,
  ensureNonEmptyString,
  ensurePythonEnvironmentName,
  ensurePositiveInteger,
  ensureRecord,
  ensureRetryCount,
  ensureRunTimeoutMinutes,
  ensureRunConflictPolicy,
} from "../Common/validation";
import { getDatabase } from "../Database/connection";
import { loggerMain } from "../Logging/logger";
import { cancelRunById, pythonRun } from "../Run/projectRunner";
import type { Dict_ProjectRun_Detail } from "../Run/types";
import { getConsolePythonCredential } from "./consoleAccount";
import { ConsoleRequestError, requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  getConsoleControlCredential,
  getConsoleWorkState,
  onConsoleWorkAvailable,
} from "./consoleControl";
import { prepareConsolePackage, stopPackagePreparation } from "./packagePreparation";
import {
  acknowledgeConsoleEvents,
  ConsoleWorkState,
  getConsoleWork,
  getPendingConsoleEvents,
  onConsoleEventSaved,
  getConsoleWorkSessionKey,
  saveConsoleEvent,
  saveConsoleWork,
  type ConsoleAssignment,
  type ConsoleWorkRecord,
} from "./workRepository";
import { flushConsoleLogs, sendConsoleFiles, stopConsoleFiles } from "./consoleWorkFiles";

const setStoppedAssignment = new Set<string>();
const mapPreparingWork = new Map<string, Promise<void>>();
let timerLogs: NodeJS.Timeout | undefined;
let timerRetry: NodeJS.Timeout | undefined;
let promiseSync: Promise<void> | undefined;
let boolStopped = true;
let boolWorkRequested = false;
let boolEventsRequested = false;
let boolContactFailureLogged = false;
let boolPreparationRefresh = false;
let boolFilesRefresh = false;
let intRetryDelayMs = 2000;
let stopWorkListener: (() => void) | undefined;
let stopEventListener: (() => void) | undefined;
let promiseLogs: Promise<void> | undefined;
let promisePreparation: Promise<void> | undefined;
let promiseFiles: Promise<void> | undefined;

function parseAssignment(value: unknown): ConsoleAssignment {
  const dictValue = ensureRecord(value, "Console assignment");
  return {
    id: ensureNonEmptyString(dictValue.id, "Assignment ID"),
    job_id: ensureNonEmptyString(dictValue.job_id, "Job ID"),
    run_id: ensureNonEmptyString(dictValue.run_id, "Run ID"),
    attempt: ensurePositiveInteger(dictValue.attempt, "Attempt"),
    package_id: ensureNonEmptyString(dictValue.package_id, "Package ID"),
    snapshot: ensureRecord(dictValue.snapshot, "Job inputs"),
  };
}

function getRunDetail(assignment: ConsoleAssignment): Dict_ProjectRun_Detail {
  const value = assignment.snapshot;
  return {
    id: 0,
    schedule_name: typeof value.schedule_name === "string" ? value.schedule_name : null,
    name: ensureNonEmptyString(value.project_name, "Package name"),
    version: ensureNonEmptyString(value.project_version, "Package version"),
    python_environment_name: ensurePythonEnvironmentName(
      value.python_environment_name,
      "Python environment",
    ),
    retry_count: ensureRetryCount(value.retry_count, "Retry Count"),
    timeout_min: ensureRunTimeoutMinutes(value.timeout_min, "Timeout"),
    builtin_log_level: ensureLogLevel(value.builtin_log_level, "Log level"),
    builtin_record_video: ensureBoolean(value.builtin_record_video, "Record video"),
    builtin_stop_shortcut: ensureBoolean(value.builtin_stop_shortcut, "Stop shortcut"),
    builtin_highlight_ui: ensureBoolean(value.builtin_highlight_ui, "Highlight UI"),
    custom_prj_args: ensureCustomProjectArgs(value.custom_prj_args, "Custom arguments"),
    run_conflict_policy: ensureRunConflictPolicy(
      value.run_conflict_policy,
      "Conflict policy",
    ),
  };
}

function ensureWorkMayStart(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): void {
  const currentCredential = getConsolePythonCredential();
  if (boolStopped || setStoppedAssignment.has(record.assignment.id))
    throw new Error("Console canceled this assignment before launch.");
  if (
    !currentCredential ||
    getConsoleWorkSessionKey(currentCredential) !== getConsoleWorkSessionKey(credential)
  )
    throw new Error("The original Console account is no longer associated.");
}

async function getStartPermit(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): Promise<Record<string, unknown>> {
  while (true) {
    ensureWorkMayStart(record, credential);
    try {
      return await requestConsole(
        credential.consoleUrl,
        "executor/work/permit/",
        credential.token,
        { assignment_id: record.assignment.id },
      );
    } catch (e: unknown) {
      const boolTemporary =
        !(e instanceof ConsoleRequestError) ||
        e.status >= 500 ||
        [
          "dispatch_paused",
          "executor_busy",
          "work_state_required",
          "control_service_unavailable",
        ].includes(e.code);
      if (!boolTemporary) throw e;
      // Repeating this assignment returns the original nonrenewable permit after a lost response.
      await new Promise<void>((resolve) => setTimeout(resolve, 2000));
    }
  }
}

async function prepareAndRun(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  let boolPrepared = false;
  try {
    const detail = getRunDetail(record.assignment);
    const strPackagePath = await prepareConsolePackage(record.assignment, credential);
    boolPrepared = true;
    ensureWorkMayStart(record, credential);
    const permit = await getStartPermit(record, credential);
    if (
      permit.assignment_id !== record.assignment.id ||
      permit.run_id !== record.assignment.run_id
    )
      throw new Error("Console returned an unrelated start permit.");
    record.permitExpiresAt = ensureNonEmptyString(
      permit.permit_expires_at,
      "Permit expiry",
    );
    record.state = ConsoleWorkState.Permitted;
    saveConsoleWork(record);
    await pythonRun(detail, {
      source: RunSource.Console,
      jobId: record.assignment.job_id,
      runId: record.assignment.run_id,
      attempt: record.assignment.attempt,
      packagePath: strPackagePath,
      beforeSpawn() {
        ensureWorkMayStart(record, credential);
        if (!record.permitExpiresAt || Date.parse(record.permitExpiresAt) <= Date.now())
          throw new Error("The Console start permit expired before process creation.");
        record.state = ConsoleWorkState.Launching;
        saveConsoleWork(record);
      },
      onStopping(reason) {
        record.stopReason = reason;
        saveConsoleWork(record);
      },
      onStarted(fact) {
        record.started = fact;
        record.state = ConsoleWorkState.Running;
        getDatabase().transaction(() => {
          saveConsoleWork(record);
          saveConsoleEvent(record, {
            kind: "started",
            occurred_at: fact.startedAt,
            started_at: fact.startedAt,
          });
        })();
      },
      onEnded(fact) {
        record.ended = fact;
        record.state = ConsoleWorkState.Finished;
        getDatabase().transaction(() => {
          saveConsoleWork(record);
          saveConsoleEvent(record, {
            kind: "ended",
            occurred_at: fact.endedAt,
            started_at: fact.startedAt,
            result:
              fact.status === "cancel"
                ? "canceled"
                : fact.status === "timeout"
                  ? "timed_out"
                  : fact.status,
            outputs_status: fact.outputs.status,
            outputs: fact.outputs.values,
            outputs_unavailable_keys: fact.outputs.unavailableKeys,
            outputs_reason: fact.outputs.reason,
            error_summary: fact.errorSummary,
          });
        })();
      },
    });
  } catch (e: unknown) {
    const boolUncertain =
      record.state === ConsoleWorkState.Launching ||
      record.state === ConsoleWorkState.Running;
    const strKind = boolUncertain
      ? "unknown"
      : boolStopped ||
          boolPrepared ||
          record.state === ConsoleWorkState.Permitted ||
          setStoppedAssignment.has(record.assignment.id)
        ? "not_started"
        : "preparation_failed";
    record.state = boolUncertain ? ConsoleWorkState.Unknown : ConsoleWorkState.Finished;
    getDatabase().transaction(() => {
      saveConsoleWork(record);
      saveConsoleEvent(record, { kind: strKind, reason: getErrorMessage(e) });
    })();
    loggerMain.warn(`Console assignment ${record.assignment.id}: ${getErrorMessage(e)}`);
  } finally {
    setStoppedAssignment.delete(record.assignment.id);
  }
}

function isCurrentControlCredential(credential: ConsoleCredentialSnapshot): boolean {
  const current = getConsoleControlCredential();
  return (
    current?.token === credential.token && current.consoleUrl === credential.consoleUrl
  );
}

async function sendPendingConsoleEvents(
  strSessionKey: string,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  while (!boolStopped) {
    const arrEvent = getPendingConsoleEvents(strSessionKey);
    if (!arrEvent.length) return;
    const response = await requestConsole(
      credential.consoleUrl,
      "executor/work/events/",
      credential.token,
      { events: arrEvent },
    );
    const arrAccepted = Array.isArray(response.accepted_event_ids)
      ? response.accepted_event_ids.filter(
          (value): value is string => typeof value === "string",
        )
      : [];
    const arrRejected = Array.isArray(response.rejected_events)
      ? response.rejected_events
          .map((value) => ensureRecord(value, "Rejected event"))
          .map((value) => ensureNonEmptyString(value.event_id, "Rejected event ID"))
      : [];
    if (!arrAccepted.length && !arrRejected.length)
      throw new Error("Console did not acknowledge the pending Run events.");
    acknowledgeConsoleEvents(arrAccepted, arrRejected);
    if (!isCurrentControlCredential(credential)) return;
  }
}

async function syncConsoleWork(
  strSessionKey: string,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  const response = await requestConsole(
    credential.consoleUrl,
    "executor/work/poll/",
    credential.token,
    getConsoleWorkState(),
  );
  if (boolStopped || !isCurrentControlCredential(credential)) return;
  if (Array.isArray(response.stop_run_ids))
    for (const value of response.stop_run_ids)
      cancelRunById(ensureNonEmptyString(value, "Stop Run ID"));
  if (Array.isArray(response.stop_assignment_ids))
    for (const value of response.stop_assignment_ids) {
      const strId = ensureNonEmptyString(value, "Stop assignment ID");
      setStoppedAssignment.add(strId);
      const record = getConsoleWork(strId);
      if (record) cancelRunById(record.assignment.run_id);
    }
  if (Array.isArray(response.assignments))
    for (const value of response.assignments) {
      const assignment = parseAssignment(value);
      if (getConsoleWork(assignment.id) || mapPreparingWork.has(assignment.id)) continue;
      const record: ConsoleWorkRecord = {
        assignment,
        sessionKey: strSessionKey,
        consoleUrl: credential.consoleUrl,
        state: ConsoleWorkState.Preparing,
        logOffsets: {},
        logsComplete: false,
      };
      saveConsoleWork(record);
      const promiseWork = prepareAndRun(record, credential).finally(() => {
        mapPreparingWork.delete(assignment.id);
      });
      mapPreparingWork.set(assignment.id, promiseWork);
    }
  if (Array.isArray(response.preparations) && response.preparations.length) {
    if (promisePreparation) {
      boolPreparationRefresh = true;
    } else {
      let boolFailed = false;
      promisePreparation = prepareRequestedPackages(response.preparations, credential)
        .catch((e: unknown) => {
          boolFailed = true;
          loggerMain.warn(`Console Package preparation: ${getErrorMessage(e)}`);
        })
        .finally(() => {
          promisePreparation = undefined;
          if (boolFailed || boolPreparationRefresh) {
            boolPreparationRefresh = false;
            requestConsoleWork(boolFailed);
          }
        });
    }
  }
  if (Array.isArray(response.file_transfers) && response.file_transfers.length) {
    if (promiseFiles) {
      boolFilesRefresh = true;
    } else {
      let boolFailed = false;
      promiseFiles = sendConsoleFiles(strSessionKey, credential, response.file_transfers)
        .catch((e: unknown) => {
          boolFailed = true;
          loggerMain.warn(`Console log/file transfer: ${getErrorMessage(e)}`);
        })
        .finally(() => {
          promiseFiles = undefined;
          if (boolFailed || boolFilesRefresh) {
            boolFilesRefresh = false;
            requestConsoleWork(boolFailed);
          }
        });
    }
  }
}

async function prepareRequestedPackages(
  values: unknown[],
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  for (const value of values) {
    if (boolStopped) return;
    const request = ensureRecord(value, "Package preparation request");
    const strId = ensureNonEmptyString(request.preparation_id, "Preparation ID");
    const inputs = ensureRecord(request.inputs, "Preparation inputs");
    let strReason = "";
    try {
      await prepareConsolePackage(
        {
          id: strId,
          job_id: "",
          run_id: "",
          attempt: 1,
          package_id: ensureNonEmptyString(inputs.package_id, "Package ID"),
          snapshot: inputs,
        },
        credential,
      );
    } catch (e: unknown) {
      strReason = getErrorMessage(e);
    }
    if (boolStopped) return;
    await requestConsole(
      credential.consoleUrl,
      `executor/packages/preparations/${encodeURIComponent(strId)}/complete/`,
      credential.token,
      { state: strReason ? "failed" : "ready", reason: strReason.slice(0, 2000) },
    );
  }
}

function requestLogFlush(): void {
  const credential = getConsoleControlCredential();
  if (boolStopped || promiseLogs || !credential) return;
  // The interval only reads local log progress; idle Runs do not issue HTTP requests.
  promiseLogs = flushConsoleLogs(getConsoleWorkSessionKey(credential), credential)
    .catch((e: unknown) => {
      loggerMain.warn(`Console logs: ${getErrorMessage(e)}`);
    })
    .finally(() => {
      promiseLogs = undefined;
    });
}

async function processConsoleUpdates(): Promise<void> {
  while (!boolStopped && (boolWorkRequested || boolEventsRequested)) {
    const credential = getConsoleControlCredential();
    if (!credential) return;
    const strSessionKey = getConsoleWorkSessionKey(credential);
    if (boolEventsRequested || getPendingConsoleEvents(strSessionKey).length) {
      boolEventsRequested = false;
      try {
        await sendPendingConsoleEvents(strSessionKey, credential);
      } catch (e: unknown) {
        boolEventsRequested = true;
        throw e;
      }
    }
    if (!isCurrentControlCredential(credential)) continue;
    if (boolWorkRequested) {
      boolWorkRequested = false;
      try {
        await syncConsoleWork(strSessionKey, credential);
      } catch (e: unknown) {
        boolWorkRequested = true;
        throw e;
      }
    }
  }
}

function scheduleConsoleRetry(): void {
  if (boolStopped || timerRetry || !getConsoleControlCredential()) return;
  timerRetry = setTimeout(() => {
    timerRetry = undefined;
    requestConsoleSync();
  }, intRetryDelayMs);
  intRetryDelayMs = Math.min(intRetryDelayMs * 2, 30_000);
}

function requestConsoleSync(): void {
  if (boolStopped || promiseSync || !getConsoleControlCredential()) return;
  let boolFailed = false;
  promiseSync = processConsoleUpdates()
    .then(() => {
      intRetryDelayMs = 2000;
      boolContactFailureLogged = false;
    })
    .catch((e: unknown) => {
      boolFailed = true;
      if (!boolContactFailureLogged) {
        boolContactFailureLogged = true;
        loggerMain.warn(`Console work contact: ${getErrorMessage(e)}`);
      }
    })
    .finally(() => {
      promiseSync = undefined;
      if (boolFailed) scheduleConsoleRetry();
      else if (boolWorkRequested || boolEventsRequested) requestConsoleSync();
    });
}

function requestConsoleWork(delayed = false): void {
  if (boolStopped) return;
  boolWorkRequested = true;
  boolEventsRequested = true;
  if (delayed) scheduleConsoleRetry();
  else {
    clearTimeout(timerRetry);
    timerRetry = undefined;
    requestConsoleSync();
    requestLogFlush();
  }
}

export function startConsoleWork(): void {
  boolStopped = false;
  stopWorkListener = onConsoleWorkAvailable(() => requestConsoleWork());
  stopEventListener = onConsoleEventSaved(() => {
    if (boolStopped) return;
    boolEventsRequested = true;
    if (!timerRetry) requestConsoleSync();
    requestLogFlush();
  });
  timerLogs = setInterval(requestLogFlush, 2000);
  requestConsoleWork();
}

export async function stopConsoleWork(): Promise<void> {
  boolStopped = true;
  stopWorkListener?.();
  stopEventListener?.();
  stopPackagePreparation();
  stopConsoleFiles();
  clearTimeout(timerRetry);
  clearInterval(timerLogs);
  await promiseSync;
  await Promise.allSettled([
    ...mapPreparingWork.values(),
    promisePreparation,
    promiseLogs,
    promiseFiles,
  ]);
}
