// FileName: consoleWork.ts

import { RunSource, type RunConfig } from "../../shared/run";
import { RunConflictPolicy } from "../../shared/runSettings";
import { ConsoleConnection } from "../../shared/consoleAccount";
import { getErrorMessage } from "../../shared/error";

import {
  ensureRecord,
  ensureExactRecord,
  ensureString,
  ensureNonEmptyString,
  ensurePythonEnvironmentName,
  ensureBoolean,
  ensurePositiveInteger,
  ensureMaxRetryCount,
  ensureRunTimeoutMinutes,
  ensureLogLevel,
  ensureRunConflictPolicy,
  ensureCustomProjectArgs,
} from "../Common/validation";
import { getDatabase } from "../Database/connection";
import { loggerMain } from "../Logging/logger";
import { startRun, cancelRunById } from "../Run/packageRunner";
import { PythonProcessNotStartedError } from "../Run/pythonProcess";

import { getLocalWaitingCount } from "../Scheduler/schedulerEngine";
import { getConsoleAccountState, getConsolePythonCredential } from "./consoleAccount";
import { ConsoleRequestError, requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  getConsoleWorkState,
  getConsoleControlCredential,
  isCurrentConsoleControlCredential,
  onConsoleWorkAvailable,
  onConsoleWorkStateReported,
} from "./consoleControl";
import { prepareConsolePackage, stopPackagePreparation } from "./packagePreparation";
import {
  ConsoleWorkState,
  type ConsoleAssignment,
  type ConsoleAssignmentData,
  type ConsoleWorkRecord,
  getConsoleWorkSessionKey,
  getConsoleWork,
  saveConsoleWork,
} from "./workRepository";
import {
  ConsoleEventKind,
  ConsoleNotStartedReason,
  type ConsoleEventData,
  onConsoleEventSaved,
  saveConsoleEvent,
} from "./eventRepository";
import { requestConsoleEvents, startConsoleEvents } from "./consoleEvents";
import { stopConsoleLogs, uploadConsoleLogs } from "./consoleLogs";
import { stopConsoleFileTransfers, sendConsoleFile } from "./consoleFileTransfers";

enum ConsolePermitWaitReason {
  DispatchPaused = "dispatch_paused",
  ExecutorBusy = "executor_busy",
  WorkStateRequired = "work_state_required",
}

interface ConsoleStartPermit {
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
const setFileTransfers = new Set<Promise<void>>();
let timerLogs: NodeJS.Timeout | undefined;
let timerRetry: NodeJS.Timeout | undefined;
let promiseSync: Promise<void> | undefined;
let boolStopped = true;
let boolWorkRequested = false;
let boolContactFailureLogged = false;
let boolPreparationRefresh = false;
let intRetryDelayMs = 2000;
let floatWorkRetryAt = 0;
let strWorkRetrySessionKey: string | undefined;
let stopWorkListener: (() => void) | undefined;
let stopEventListener: (() => void) | undefined;
let promiseLogs: Promise<void> | undefined;
let promisePreparation: Promise<void> | undefined;

function parseAssignmentData(value: unknown): ConsoleAssignmentData {
  const dictValue = ensureRecord(value, "Console assignment");
  return {
    id: ensureNonEmptyString(dictValue.id, "Assignment ID"),
    job_id: ensureNonEmptyString(dictValue.job_id, "Job ID"),
    run_id: ensureNonEmptyString(dictValue.run_id, "Run ID"),
    attempt_number: ensurePositiveInteger(dictValue.attempt_number, "Attempt"),
    package_id: ensureNonEmptyString(dictValue.package_id, "Package ID"),
    snapshot: ensureRecord(dictValue.snapshot, "Run snapshot"),
  };
}

function parseRunAssignment(assignment: ConsoleAssignmentData): ConsoleAssignment {
  const snapshot = assignment.snapshot;
  const arrCustomProjectArg = ensureCustomProjectArgs(
    snapshot.custom_prj_args,
    "Custom arguments",
  );
  const setCustomProjectArgKey = new Set(arrCustomProjectArg.map(([strKey]) => strKey));
  const dictEmailOutputKeys = ensureExactRecord(
    snapshot.email_output_keys,
    ["completed", "error"],
    "Run email output keys",
  );
  function parseOutputKeyList(value: unknown): string[] {
    if (!Array.isArray(value)) throw new Error("Run email output keys must be an array.");
    const arrKey = value.map((key: unknown) => ensureString(key, "Run email output key"));
    if (new Set(arrKey).size !== arrKey.length)
      throw new Error("Run email output keys must be unique.");
    if (arrKey.some((strKey) => !setCustomProjectArgKey.has(strKey)))
      throw new Error("Run email output keys must refer to custom arguments.");
    return arrKey;
  }

  return {
    ...assignment,
    snapshot: {
      project_name: ensureNonEmptyString(snapshot.project_name, "Project name"),
      project_version: ensureNonEmptyString(snapshot.project_version, "Project version"),
      sha256: ensureNonEmptyString(snapshot.sha256, "Package SHA256"),
      email_output_keys: {
        completed: parseOutputKeyList(dictEmailOutputKeys.completed),
        error: parseOutputKeyList(dictEmailOutputKeys.error),
      },
      schedule_name:
        typeof snapshot.schedule_name === "string" ? snapshot.schedule_name : null,
      python_environment_name: ensurePythonEnvironmentName(
        snapshot.python_environment_name,
        "Python environment",
      ),
      max_retry_count: ensureMaxRetryCount(snapshot.max_retry_count, "Max retry count"),
      timeout_min: ensureRunTimeoutMinutes(snapshot.timeout_min, "Timeout"),
      builtin_log_level: ensureLogLevel(snapshot.builtin_log_level, "Log level"),
      builtin_record_video: ensureBoolean(snapshot.builtin_record_video, "Record video"),
      builtin_stop_shortcut: ensureBoolean(snapshot.builtin_stop_shortcut, "Stop shortcut"),
      builtin_highlight_ui: ensureBoolean(snapshot.builtin_highlight_ui, "Highlight UI"),
      custom_prj_args: arrCustomProjectArg,
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
  if (getConsoleAccountState().connection === ConsoleConnection.AccessUnavailable)
    throw new Error("Console access is unavailable. This Run cannot start.");
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

async function requestStartPermit(
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
        // Server JSON timestamps lose sub-millisecond precision; keep both bounds safe.
        earliestStartMs: intEarliestStart + 1,
        expiresAtMs: intExpiresAt,
        // Subtract the full request duration; the outgoing request and response may take different amounts of time.
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

async function prepareAndStartRun(
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
      email_output_keys: emailOutputKeys,
      ...runSettings
    } = assignment.snapshot;
    const detail: RunConfig = {
      ...runSettings,
      local_package_id: null,
      project_name: strProjectName,
      project_version: strProjectVersion,
    };
    const strPackagePath = await prepareConsolePackage(
      {
        packageId: assignment.package_id,
        projectName: detail.project_name,
        projectVersion: detail.project_version,
        sha256: strSha256,
      },
      detail.python_environment_name,
      credential,
    );
    boolPrepared = true;
    ensureWorkMayStart(record, credential);
    const permit = await requestStartPermit(record, credential);
    record.state = ConsoleWorkState.Permitted;
    saveConsoleWork(record);
    await startRun(detail, {
      source: RunSource.Console,
      jobId: record.assignment.job_id,
      runId: record.assignment.run_id,
      attemptNumber: record.assignment.attempt_number,
      packagePath: strPackagePath,
      emailOutputKeys,
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
            status: fact.status,
            outputs: fact.outputs,
            email_output_context: fact.emailOutputContext,
            error_summary: fact.errorSummary,
          });
        })();
      },
    });
  } catch (e: unknown) {
    const boolUncertain =
      !(e instanceof PythonProcessNotStartedError) &&
      (record.state === ConsoleWorkState.Launching ||
        record.state === ConsoleWorkState.Running);
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

async function prepareRequestedPackages(
  values: unknown[],
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  for (const value of values) {
    if (boolStopped) return;
    const request = ensureRecord(value, "Package preparation request");
    const strId = ensureNonEmptyString(request.preparation_id, "Preparation ID");
    const snapshot = ensureRecord(request.snapshot, "Preparation snapshot");
    let strReason = "";
    try {
      await prepareConsolePackage(
        {
          packageId: ensureNonEmptyString(snapshot.package_id, "Package ID"),
          projectName: ensureNonEmptyString(snapshot.project_name, "Project name"),
          projectVersion: ensureNonEmptyString(snapshot.project_version, "Project version"),
          sha256: ensureNonEmptyString(snapshot.sha256, "Package SHA256"),
        },
        ensurePythonEnvironmentName(snapshot.python_environment_name, "Python environment"),
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

function requestLogUpload(): void {
  const credential = getConsoleControlCredential();
  if (boolStopped || promiseLogs || !credential) return;
  // The interval only reads local log progress; idle Runs do not issue HTTP requests.
  promiseLogs = uploadConsoleLogs(getConsoleWorkSessionKey(credential), credential)
    .catch((e: unknown) => {
      loggerMain.warn(`Console logs: ${getErrorMessage(e)}`);
    })
    .finally(() => {
      promiseLogs = undefined;
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
  if (boolStopped || !isCurrentConsoleControlCredential(credential)) return;
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
        logsFinished: false,
      };
      saveConsoleWork(record);
      const promiseWork = prepareAndStartRun(record, credential).finally(() => {
        mapPreparingWork.delete(assignment.id);
      });
      mapPreparingWork.set(assignment.id, promiseWork);
    }
  if (Array.isArray(response.preparations) && response.preparations.length) {
    if (promisePreparation) {
      boolPreparationRefresh = true;
    } else {
      let boolFailed = false;
      let retryError: unknown;
      promisePreparation = prepareRequestedPackages(response.preparations, credential)
        .catch((e: unknown) => {
          boolFailed = true;
          retryError = e;
          loggerMain.warn(`Console Package preparation: ${getErrorMessage(e)}`);
        })
        .finally(() => {
          promisePreparation = undefined;
          if (boolFailed || boolPreparationRefresh) {
            boolPreparationRefresh = false;
            requestConsoleWork(
              boolFailed && isCurrentConsoleControlCredential(credential)
                ? retryError
                : undefined,
            );
          }
        });
    }
  }
  if (Array.isArray(response.file_transfers))
    for (const transfer of response.file_transfers) {
      const promiseFile = sendConsoleFile(strSessionKey, credential, transfer)
        .catch((e: unknown) => {
          loggerMain.warn(`Console log/file transfer: ${getErrorMessage(e)}`);
          requestConsoleWork(isCurrentConsoleControlCredential(credential) ? e : undefined);
        })
        .finally(() => setFileTransfers.delete(promiseFile));
      setFileTransfers.add(promiseFile);
    }
}

async function processConsoleUpdates(credential: ConsoleCredentialSnapshot): Promise<void> {
  while (
    !boolStopped &&
    boolWorkRequested &&
    isCurrentConsoleControlCredential(credential) &&
    performance.now() >= floatWorkRetryAt
  ) {
    boolWorkRequested = false;
    try {
      await syncConsoleWork(getConsoleWorkSessionKey(credential), credential);
    } catch (e: unknown) {
      boolWorkRequested = true;
      throw e;
    }
  }
}

function deferConsoleWork(error: unknown): void {
  const credential = getConsoleControlCredential();
  if (!credential) return;
  const strSessionKey = getConsoleWorkSessionKey(credential);
  if (strWorkRetrySessionKey !== strSessionKey) {
    clearTimeout(timerRetry);
    timerRetry = undefined;
    strWorkRetrySessionKey = strSessionKey;
    floatWorkRetryAt = 0;
    intRetryDelayMs = 2000;
    boolContactFailureLogged = false;
  }
  const intRetryAfterMs = error instanceof ConsoleRequestError ? error.retryAfterMs : 0;
  floatWorkRetryAt = Math.max(
    floatWorkRetryAt,
    performance.now() + Math.max(intRetryDelayMs, intRetryAfterMs),
  );
  intRetryDelayMs = Math.min(intRetryDelayMs * 2, 30_000);
}

function requestConsoleSync(): void {
  const credential = getConsoleControlCredential();
  if (boolStopped || promiseSync || !credential || !boolWorkRequested) return;
  const strSessionKey = getConsoleWorkSessionKey(credential);
  if (strWorkRetrySessionKey !== strSessionKey) {
    clearTimeout(timerRetry);
    timerRetry = undefined;
    strWorkRetrySessionKey = strSessionKey;
    floatWorkRetryAt = 0;
    intRetryDelayMs = 2000;
    boolContactFailureLogged = false;
  }
  const floatRemainingMs = floatWorkRetryAt - performance.now();
  if (floatRemainingMs > 0) {
    // Notifications mark pending work but do not shorten the delay before retrying a failed request.
    timerRetry ??= setTimeout(
      () => {
        timerRetry = undefined;
        requestConsoleSync();
      },
      Math.min(floatRemainingMs, 2_147_483_647),
    );
    return;
  }
  clearTimeout(timerRetry);
  timerRetry = undefined;
  promiseSync = processConsoleUpdates(credential)
    .then(() => {
      if (!isCurrentConsoleControlCredential(credential)) return;
      intRetryDelayMs = 2000;
      boolContactFailureLogged = false;
    })
    .catch((e: unknown) => {
      if (!isCurrentConsoleControlCredential(credential)) return;
      deferConsoleWork(e);
      if (!boolContactFailureLogged) {
        boolContactFailureLogged = true;
        loggerMain.warn(`Console work contact: ${getErrorMessage(e)}`);
      }
    })
    .finally(() => {
      promiseSync = undefined;
      if (boolWorkRequested) requestConsoleSync();
    });
}

function requestConsoleWork(error?: unknown): void {
  if (boolStopped) return;
  boolWorkRequested = true;
  if (error !== undefined) deferConsoleWork(error);
  requestConsoleSync();
  requestLogUpload();
  requestConsoleEvents();
}

export function startConsoleWork(): void {
  boolStopped = false;
  intRetryDelayMs = 2000;
  floatWorkRetryAt = 0;
  strWorkRetrySessionKey = undefined;
  boolContactFailureLogged = false;
  stopWorkListener = onConsoleWorkAvailable(() => requestConsoleWork());
  stopEventListener = onConsoleEventSaved(requestLogUpload);
  timerLogs = setInterval(requestLogUpload, 2000);
  startConsoleEvents();
  requestConsoleWork();
}

export async function stopConsoleWork(): Promise<void> {
  boolStopped = true;
  for (const checkRetry of mapPermitWaiter.values()) checkRetry();
  stopWorkListener?.();
  stopEventListener?.();
  stopPackagePreparation();
  stopConsoleLogs();
  stopConsoleFileTransfers();
  clearTimeout(timerRetry);
  clearInterval(timerLogs);
  timerRetry = undefined;
  boolWorkRequested = false;
  await promiseSync;
  await Promise.allSettled([
    ...mapPreparingWork.values(),
    promisePreparation,
    promiseLogs,
    ...setFileTransfers,
  ]);
}
