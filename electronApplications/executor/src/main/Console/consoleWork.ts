// FileName: consoleWork.ts

import { RunSource } from "../../shared/run";
import { RunConflictPolicy } from "../../shared/runOptions";
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
import type { ProjectRunDetails } from "../Run/types";
import { getLocalWaitingCount } from "../Scheduler/schedulerEngine";
import { getConsolePythonCredential } from "./consoleAccount";
import { ConsoleRequestError, requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  getConsoleControlCredential,
  getConsoleWorkState,
  onConsoleWorkAvailable,
  onConsoleWorkStateReported,
} from "./consoleControl";
import { prepareConsolePackage, stopPackagePreparation } from "./packagePreparation";
import {
  acknowledgeConsoleEvents,
  ConsoleWorkState,
  ConsoleEventKind,
  ConsoleNotStartedReason,
  getConsoleWork,
  getPendingConsoleEvents,
  onConsoleEventSaved,
  getConsoleWorkSessionKey,
  saveConsoleEvent,
  saveConsoleWork,
  type ConsoleEventData,
  type ConsoleAssignment,
  type ConsoleAssignmentData,
  type ConsoleWorkRecord,
} from "./workRepository";
import { flushConsoleLogs, sendConsoleFiles, stopConsoleFiles } from "./consoleWorkFiles";

enum ConsolePermitWaitReason {
  DispatchPaused = "dispatch_paused",
  ExecutorBusy = "executor_busy",
  WorkStateRequired = "work_state_required",
}

interface ConsoleStartPermit {
  expiresAt: string;
  earliestStartMs: number;
  expiresAtMs: number;
  monotonicDeadlineMs: number;
}

class ConsoleStartConflictError extends Error {}

const INT_MIN_PERMIT_RETRY_MS = 2000;
const INT_MAX_PERMIT_RETRY_MS = 30_000;
const setStoppedAssignment = new Set<string>();
const mapPermitWaiter = new Map<string, () => void>();
const mapPreparingWork = new Map<string, Promise<void>>();
let timerLogs: NodeJS.Timeout | undefined;
let timerRetry: NodeJS.Timeout | undefined;
let timerEventRetry: NodeJS.Timeout | undefined;
let promiseSync: Promise<void> | undefined;
let promiseEvents: Promise<void> | undefined;
let boolStopped = true;
let boolWorkRequested = false;
let boolEventsRequested = false;
let boolContactFailureLogged = false;
let boolEventFailureLogged = false;
let boolPreparationRefresh = false;
let boolFilesRefresh = false;
let intRetryDelayMs = 2000;
let intEventRetryDelayMs = 2000;
let stopWorkListener: (() => void) | undefined;
let stopEventListener: (() => void) | undefined;
let promiseLogs: Promise<void> | undefined;
let promisePreparation: Promise<void> | undefined;
let promiseFiles: Promise<void> | undefined;

function parseAssignmentData(value: unknown): ConsoleAssignmentData {
  const dictValue = ensureRecord(value, "Console assignment");
  return {
    id: ensureNonEmptyString(dictValue.id, "Assignment ID"),
    job_id: ensureNonEmptyString(dictValue.job_id, "Job ID"),
    run_id: ensureNonEmptyString(dictValue.run_id, "Run ID"),
    attempt: ensurePositiveInteger(dictValue.attempt, "Attempt"),
    package_id: ensureNonEmptyString(dictValue.package_id, "Package ID"),
    snapshot: ensureRecord(dictValue.snapshot, "Run snapshot"),
  };
}

function parseRunAssignment(assignment: ConsoleAssignmentData): ConsoleAssignment {
  const snapshot = assignment.snapshot;
  return {
    ...assignment,
    snapshot: {
      project_name: ensureNonEmptyString(snapshot.project_name, "Package name"),
      project_version: ensureNonEmptyString(snapshot.project_version, "Package version"),
      sha256: ensureNonEmptyString(snapshot.sha256, "Package SHA256"),
      schedule_name:
        typeof snapshot.schedule_name === "string" ? snapshot.schedule_name : null,
      python_environment_name: ensurePythonEnvironmentName(
        snapshot.python_environment_name,
        "Python environment",
      ),
      retry_count: ensureRetryCount(snapshot.retry_count, "Retry Count"),
      timeout_min: ensureRunTimeoutMinutes(snapshot.timeout_min, "Timeout"),
      builtin_log_level: ensureLogLevel(snapshot.builtin_log_level, "Log level"),
      builtin_record_video: ensureBoolean(snapshot.builtin_record_video, "Record video"),
      builtin_stop_shortcut: ensureBoolean(snapshot.builtin_stop_shortcut, "Stop shortcut"),
      builtin_highlight_ui: ensureBoolean(snapshot.builtin_highlight_ui, "Highlight UI"),
      custom_prj_args: ensureCustomProjectArgs(
        snapshot.custom_prj_args,
        "Custom arguments",
      ),
      run_conflict_policy: ensureRunConflictPolicy(
        snapshot.run_conflict_policy,
        "Conflict policy",
      ),
    },
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

function validateStartPermitTime(permit: ConsoleStartPermit, startedAt: string): void {
  if (performance.now() >= permit.monotonicDeadlineMs)
    throw new Error(
      "The Console start permit has too little time remaining. Run the task again.",
    );
  const intStartedAt = Date.parse(startedAt);
  if (intStartedAt < permit.earliestStartMs || intStartedAt >= permit.expiresAtMs)
    throw new Error(
      "Executor and Console clocks are out of sync. " +
        "Synchronize both computers' clocks, then run the task again.",
    );
}

async function getStartPermit(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): Promise<ConsoleStartPermit> {
  function parsePermitTime(value: unknown, sourceName: string): number {
    const strTime = ensureNonEmptyString(value, sourceName);
    const intTime = Date.parse(strTime);
    if (!Number.isFinite(intTime) || !/(?:Z|[+-]\d{2}:\d{2})$/.test(strTime))
      throw new Error(`Console returned an invalid ${sourceName}.`);
    return intTime;
  }

  let intRetryDelayMs = INT_MIN_PERMIT_RETRY_MS;
  let boolWorkChanged = false;
  let boolStateReported = false;
  let checkRetry: (() => void) | undefined;
  const stopWorkListener = onConsoleWorkAvailable(() => {
    boolWorkChanged = true;
    checkRetry?.();
  });
  const stopStateListener = onConsoleWorkStateReported(() => {
    boolStateReported = true;
    checkRetry?.();
  });
  mapPermitWaiter.set(record.assignment.id, () => checkRetry?.());

  function waitForRetry(
    delayMs: number,
    waitReason: ConsolePermitWaitReason | undefined,
  ): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const floatEarliestRetryAt = performance.now() + INT_MIN_PERMIT_RETRY_MS;
      let floatRetryAt = performance.now() + delayMs;
      let timer: NodeJS.Timeout | undefined;
      function checkPermitRetry(): void {
        clearTimeout(timer);
        try {
          ensureWorkMayStart(record, credential);
        } catch (e: unknown) {
          checkRetry = undefined;
          reject(e);
          return;
        }
        if (
          waitReason !== undefined &&
          (boolWorkChanged ||
            (waitReason !== ConsolePermitWaitReason.DispatchPaused && boolStateReported))
        )
          floatRetryAt = Math.min(floatRetryAt, floatEarliestRetryAt);
        const floatRemainingMs = floatRetryAt - performance.now();
        if (floatRemainingMs <= 0) {
          checkRetry = undefined;
          resolve();
        } else {
          // Long Retry-After values still allow regular local cancellation checks.
          timer = setTimeout(
            checkPermitRetry,
            Math.min(floatRemainingMs, INT_MAX_PERMIT_RETRY_MS),
          );
        }
      }
      checkRetry = checkPermitRetry;
      checkPermitRetry();
    });
  }

  try {
    while (true) {
      ensureWorkMayStart(record, credential);
      boolWorkChanged = false;
      boolStateReported = false;
      const floatRequestedAt = performance.now();
      let response: Record<string, unknown>;
      try {
        response = await requestConsole(
          credential.consoleUrl,
          "executor/work/permit/",
          credential.token,
          { assignment_id: record.assignment.id },
        );
      } catch (e: unknown) {
        const waitReason =
          e instanceof ConsoleRequestError && e.status === 409
            ? Object.values(ConsolePermitWaitReason).find((reason) => reason === e.code)
            : undefined;
        const boolTemporary =
          !(e instanceof ConsoleRequestError) ||
          e.status === 429 ||
          e.status >= 500 ||
          (e.status === 409 && e.code === "control_service_unavailable");
        if (waitReason === undefined && !boolTemporary) throw e;
        const intRetryAfterMs = e instanceof ConsoleRequestError ? e.retryAfterMs : 0;
        // A retry requests the original assignment; it never renews an issued permit.
        await waitForRetry(
          Math.max(
            intRetryAfterMs,
            waitReason === undefined ? intRetryDelayMs : INT_MAX_PERMIT_RETRY_MS,
          ),
          intRetryAfterMs === 0 ? waitReason : undefined,
        );
        intRetryDelayMs =
          waitReason === undefined
            ? Math.min(intRetryDelayMs * 2, INT_MAX_PERMIT_RETRY_MS)
            : INT_MIN_PERMIT_RETRY_MS;
        continue;
      }
      // Validate successful responses outside the transport retry path.
      if (
        response.assignment_id !== record.assignment.id ||
        response.run_id !== record.assignment.run_id
      )
        throw new Error("Console returned an unrelated start permit.");
      const intExpiresAt = parsePermitTime(response.permit_expires_at, "permit expiry");
      const intEarliestStart = parsePermitTime(
        response.start_evidence_not_before,
        "earliest start time",
      );
      const intServerTime = parsePermitTime(response.server_time, "server time");
      if (intEarliestStart >= intExpiresAt)
        throw new Error("Console returned an invalid start permission window.");
      const permit: ConsoleStartPermit = {
        expiresAt: new Date(intExpiresAt).toISOString(),
        // Server JSON timestamps lose sub-millisecond precision; keep both bounds safe.
        earliestStartMs: intEarliestStart + 1,
        expiresAtMs: intExpiresAt,
        // Subtract the full request duration rather than assume symmetric network delay.
        monotonicDeadlineMs: floatRequestedAt + (intExpiresAt - intServerTime - 1),
      };
      validateStartPermitTime(permit, new Date().toISOString());
      return permit;
    }
  } finally {
    stopWorkListener();
    stopStateListener();
    mapPermitWaiter.delete(record.assignment.id);
  }
}

async function prepareAndRun(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  let boolPrepared = false;
  try {
    const assignment = parseRunAssignment(record.assignment);
    const {
      project_name: strProjectName,
      project_version: strProjectVersion,
      sha256: strSha256,
      ...runSettings
    } = assignment.snapshot;
    const detail: ProjectRunDetails = {
      ...runSettings,
      id: 0,
      name: strProjectName,
      version: strProjectVersion,
    };
    const strPackagePath = await prepareConsolePackage(
      {
        id: assignment.package_id,
        name: detail.name,
        version: detail.version,
        sha256: strSha256,
      },
      detail.python_environment_name,
      credential,
    );
    boolPrepared = true;
    ensureWorkMayStart(record, credential);
    const permit = await getStartPermit(record, credential);
    record.permitExpiresAt = permit.expiresAt;
    record.state = ConsoleWorkState.Permitted;
    saveConsoleWork(record);
    await pythonRun(detail, {
      source: RunSource.Console,
      consoleUrl: credential.consoleUrl,
      jobId: record.assignment.job_id,
      runId: record.assignment.run_id,
      attempt: record.assignment.attempt,
      packagePath: strPackagePath,
      beforeSpawn(boolOtherRunActive, startedAt) {
        ensureWorkMayStart(record, credential);
        validateStartPermitTime(permit, startedAt);
        if (
          detail.run_conflict_policy !== RunConflictPolicy.Concurrent &&
          (boolOtherRunActive || getLocalWaitingCount() > 0)
        )
          throw new ConsoleStartConflictError(
            "Local running or waiting work takes priority.",
          );
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
            kind: ConsoleEventKind.Started,
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
            kind: ConsoleEventKind.Ended,
            occurred_at: fact.endedAt,
            started_at: fact.startedAt,
            result: fact.status,
            outputs: fact.outputs,
            error_summary: fact.errorSummary,
          });
        })();
      },
    });
  } catch (e: unknown) {
    const boolUncertain =
      record.state === ConsoleWorkState.Launching ||
      record.state === ConsoleWorkState.Running;
    const boolLocalConflict = !boolUncertain && e instanceof ConsoleStartConflictError;
    const strReason = getErrorMessage(e);
    let event: ConsoleEventData;
    if (boolUncertain) {
      event = { kind: ConsoleEventKind.Unknown, reason: strReason };
    } else if (boolLocalConflict) {
      event = {
        kind: ConsoleEventKind.NotStarted,
        reason: strReason,
        not_started_reason: ConsoleNotStartedReason.LocalConflict,
      };
    } else if (
      boolStopped ||
      boolPrepared ||
      record.state === ConsoleWorkState.Permitted ||
      setStoppedAssignment.has(record.assignment.id)
    ) {
      event = { kind: ConsoleEventKind.NotStarted, reason: strReason };
    } else {
      event = { kind: ConsoleEventKind.PreparationFailed, reason: strReason };
    }
    record.state = boolUncertain ? ConsoleWorkState.Unknown : ConsoleWorkState.Finished;
    getDatabase().transaction(() => {
      saveConsoleWork(record);
      saveConsoleEvent(record, event);
    })();
    const strMessage = `Console assignment ${record.assignment.id}: ${strReason}`;
    if (boolLocalConflict) loggerMain.info(strMessage);
    else loggerMain.warn(strMessage);
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
): Promise<boolean> {
  const arrEvent = getPendingConsoleEvents(strSessionKey);
  if (!arrEvent.length) return false;
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
  return isCurrentControlCredential(credential);
}

function requestConsoleEvents(): void {
  if (boolStopped) return;
  boolEventsRequested = true;
  const credential = getConsoleControlCredential();
  if (promiseEvents || timerEventRetry || !credential) return;
  boolEventsRequested = false;
  let boolFailed = false;
  // Send one bounded batch at a time without holding up control synchronization.
  promiseEvents = sendPendingConsoleEvents(getConsoleWorkSessionKey(credential), credential)
    .then((boolMoreEvents) => {
      boolEventsRequested ||= boolMoreEvents;
      intEventRetryDelayMs = 2000;
      boolEventFailureLogged = false;
    })
    .catch((e: unknown) => {
      boolFailed = true;
      boolEventsRequested = true;
      if (!boolEventFailureLogged) {
        boolEventFailureLogged = true;
        loggerMain.warn(`Console Run events: ${getErrorMessage(e)}`);
      }
    })
    .finally(() => {
      promiseEvents = undefined;
      if (boolStopped) return;
      if (boolFailed) {
        if (!getConsoleControlCredential()) return;
        timerEventRetry = setTimeout(() => {
          timerEventRetry = undefined;
          requestConsoleEvents();
        }, intEventRetryDelayMs);
        intEventRetryDelayMs = Math.min(intEventRetryDelayMs * 2, 30_000);
      } else if (boolEventsRequested) {
        requestConsoleEvents();
      }
    });
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
  if (!Array.isArray(response.stop_requests))
    throw new Error("Console returned invalid stop requests.");
  for (const value of response.stop_requests) {
    const request = ensureRecord(value, "Console stop request");
    const strAssignmentId = ensureNonEmptyString(
      request.assignment_id,
      "Stop assignment ID",
    );
    const strRunId = ensureNonEmptyString(request.run_id, "Stop Run ID");
    const record = getConsoleWork(strAssignmentId);
    if (
      record &&
      (record.sessionKey !== strSessionKey || record.assignment.run_id !== strRunId)
    )
      throw new Error("Console returned a stop request for a different local assignment.");
    if (mapPreparingWork.has(strAssignmentId)) {
      setStoppedAssignment.add(strAssignmentId);
      mapPermitWaiter.get(strAssignmentId)?.();
    }
    cancelRunById(strRunId);
  }
  if (Array.isArray(response.assignments))
    for (const value of response.assignments) {
      const assignment = parseAssignmentData(value);
      if (getConsoleWork(assignment.id) || mapPreparingWork.has(assignment.id)) continue;
      const record: ConsoleWorkRecord = {
        assignment,
        sessionKey: strSessionKey,
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
          id: ensureNonEmptyString(inputs.package_id, "Package ID"),
          name: ensureNonEmptyString(inputs.project_name, "Package name"),
          version: ensureNonEmptyString(inputs.project_version, "Package version"),
          sha256: ensureNonEmptyString(inputs.sha256, "Package SHA256"),
        },
        ensurePythonEnvironmentName(inputs.python_environment_name, "Python environment"),
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
  while (!boolStopped && boolWorkRequested) {
    const credential = getConsoleControlCredential();
    if (!credential) return;
    boolWorkRequested = false;
    try {
      await syncConsoleWork(getConsoleWorkSessionKey(credential), credential);
    } catch (e: unknown) {
      boolWorkRequested = true;
      throw e;
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
      else if (boolWorkRequested) requestConsoleSync();
    });
}

function requestConsoleWork(delayed = false): void {
  if (boolStopped) return;
  boolWorkRequested = true;
  if (delayed) scheduleConsoleRetry();
  else {
    clearTimeout(timerRetry);
    timerRetry = undefined;
    requestConsoleSync();
    requestLogFlush();
  }
  requestConsoleEvents();
}

export function startConsoleWork(): void {
  boolStopped = false;
  intRetryDelayMs = 2000;
  intEventRetryDelayMs = 2000;
  boolContactFailureLogged = false;
  boolEventFailureLogged = false;
  stopWorkListener = onConsoleWorkAvailable(() => requestConsoleWork());
  stopEventListener = onConsoleEventSaved(() => {
    requestConsoleEvents();
    requestLogFlush();
  });
  timerLogs = setInterval(requestLogFlush, 2000);
  requestConsoleWork();
}

export async function stopConsoleWork(): Promise<void> {
  boolStopped = true;
  for (const checkRetry of mapPermitWaiter.values()) checkRetry();
  stopWorkListener?.();
  stopEventListener?.();
  const promisePackageCleanup = stopPackagePreparation();
  stopConsoleFiles();
  clearTimeout(timerRetry);
  clearTimeout(timerEventRetry);
  clearInterval(timerLogs);
  timerRetry = undefined;
  timerEventRetry = undefined;
  boolWorkRequested = false;
  boolEventsRequested = false;
  await Promise.all([promiseSync, promiseEvents]);
  await Promise.allSettled([
    promisePackageCleanup,
    ...mapPreparingWork.values(),
    promisePreparation,
    promiseLogs,
    promiseFiles,
  ]);
}
