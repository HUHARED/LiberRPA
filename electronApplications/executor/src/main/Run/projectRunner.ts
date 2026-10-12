// FileName: projectRunner.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs";
import { performance } from "perf_hooks";

import { getErrorMessage } from "../../shared/error";
import {
  RunSource,
  RunOutputsStatus,
  type RunOutputs,
  type ProjectRunConfig,
  RunStatus,
  type RunTerminalStatus,
  JobQueueState,
  type JobQueueItem,
} from "../../shared/run";
import { isProcessRunning } from "../Common/process";
import { getEffectiveProjectLogFolderPath } from "../Config/executorConfig";
import { getPythonEnvironmentPath } from "../Config/environment";
import { dbInsertRunHistory, dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { getDatabase } from "../Database/connection";
import { validatePackageLiberrpaRequirement } from "../Package/packageMetadata";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { notifyRunEnded, notifyRunActivityChanged, notifyRunFinished } from "./lifecycle";
import {
  PythonProcessNotStartedError,
  type PythonProcessDiagnosticOutput,
  spawnProjectPythonProcess,
  logPythonDiagnosticOutput,
  requestPythonTermination,
  waitForPythonProcessTermination,
  terminatePythonProcessAfterStartupFailure,
} from "./pythonProcess";
import {
  ExecutorRunStateStatus,
  type ExecutorRunState,
  createExecutorRunStatePath,
  removeExecutorRunStateFile,
  parseExecutorRunTimestamp,
  readExecutorRunState,
  waitForExecutorRunStateAvailable,
} from "./runState";
import { RunTerminationReason, type RunEndedFact, type RunExecutionContext } from "./types";

import { hasRecoveredRun } from "./recoveredRuns";

interface ActiveProjectRun {
  processPy: ChildProcessWithoutNullStreams;
  runId: string;
  source: RunSource;
  queueItem?: JobQueueItem;
  onStopping?: RunExecutionContext["onStopping"];
  terminationReason?: RunTerminationReason;
  terminationPromise?: Promise<void>;
  forceTerminationRequired: boolean;
}

const mapActiveRunByHistoryId = new Map<number, ActiveProjectRun>();
const mapActiveRunByRunId = new Map<string, ActiveProjectRun>();
const mapStartingJobQueueItem = new Map<string, JobQueueItem>();

const mapStartingRun = new Map<
  string,
  { localProjectId: number | null; source: RunSource }
>();
const setStartingRunPromise = new Set<Promise<void>>();
let boolProjectRunShutdownStarted = false;
let promiseConsoleAccountTransition: Promise<void> | undefined;
let finishConsoleAccountTransition: (() => void) | undefined;

export function hasActiveProjectRun(excludeCurrentStart = false): boolean {
  return (
    mapStartingRun.size > (excludeCurrentStart ? 1 : 0) ||
    mapActiveRunByRunId.size !== 0 ||
    hasRecoveredRun()
  );
}

export function isProjectRunStarting(projectId: number): boolean {
  return [...mapStartingRun.values()].some((run) => run.localProjectId === projectId);
}

export function getActiveJobQueueItems(): JobQueueItem[] {
  const arrItem = [...mapStartingJobQueueItem.values()].map((item) => ({ ...item }));
  for (const activeRun of mapActiveRunByRunId.values()) {
    if (activeRun.queueItem === undefined) continue;
    arrItem.push({
      ...activeRun.queueItem,
      state:
        activeRun.terminationReason === undefined
          ? JobQueueState.Running
          : JobQueueState.Stopping,
    });
  }
  return arrItem;
}

export function getActiveConsoleRunIds(): string[] {
  return [...mapActiveRunByRunId.values()]
    .filter((activeRun) => activeRun.source === RunSource.Console)
    .map((activeRun) => activeRun.runId);
}

export function getLocalActiveRunCount(): number {
  const setLocalRunId = new Set<string>();
  for (const [runId, run] of mapStartingRun) {
    if (run.source === RunSource.Local) setLocalRunId.add(runId);
  }
  for (const run of mapActiveRunByRunId.values()) {
    if (run.source === RunSource.Local) setLocalRunId.add(run.runId);
  }
  return setLocalRunId.size;
}

export function beginConsoleAccountTransition(): void {
  if (hasActiveProjectRun()) {
    throw new Error(
      "Wait for all actual Runs to finish or stop them before signing out or changing the Console address.",
    );
  }
  if (promiseConsoleAccountTransition !== undefined) {
    throw new Error("A Console account change is already in progress.");
  }
  promiseConsoleAccountTransition = new Promise<void>((resolve) => {
    finishConsoleAccountTransition = resolve;
  });
}

export function endConsoleAccountTransition(): void {
  finishConsoleAccountTransition?.();
  finishConsoleAccountTransition = undefined;
  promiseConsoleAccountTransition = undefined;
}

function trackActiveProjectRun(activeRun: ActiveProjectRun): void {
  mapActiveRunByRunId.set(activeRun.runId, activeRun);
  activeRun.processPy.once("close", () => {
    if (mapActiveRunByRunId.get(activeRun.runId) === activeRun) {
      mapActiveRunByRunId.delete(activeRun.runId);
      notifyRunActivityChanged();
    }
  });
}

function getRequestedRunStatus(
  terminationReason: RunTerminationReason | undefined,
): RunStatus.Canceled | RunStatus.TimedOut | undefined {
  if (terminationReason === RunTerminationReason.Timeout) {
    return RunStatus.TimedOut;
  }
  if (terminationReason !== undefined) {
    return RunStatus.Canceled;
  }
  return undefined;
}

function requestProjectRunTermination(
  activeRun: ActiveProjectRun,
  reason: RunTerminationReason,
): Promise<void> {
  if (activeRun.terminationPromise !== undefined) {
    return activeRun.terminationPromise;
  }
  if (!isProcessRunning(activeRun.processPy)) {
    return Promise.resolve();
  }

  activeRun.terminationReason = reason;
  activeRun.onStopping?.(reason);
  if (!requestPythonTermination(activeRun.processPy, activeRun.runId)) {
    loggerMain.debug(
      `Python process ${activeRun.runId} cannot receive the termination message.`,
    );
  }

  const promiseTermination = waitForPythonProcessTermination(
    activeRun.processPy,
    activeRun.runId,
    () => {
      activeRun.forceTerminationRequired = true;
    },
  );
  activeRun.terminationPromise = promiseTermination;
  notifyRunActivityChanged();
  return promiseTermination;
}

async function waitForInitialRunState({
  processPy,
  getProcessError,
  runId,
  runStatePath,
  packageName,
  packageVersion,
  expectedStartedAt,
  expectedLogRootPath,
  diagnosticOutput,
}: {
  processPy: ChildProcessWithoutNullStreams;
  getProcessError: () => Error | undefined;
  runId: string;
  runStatePath: string;
  packageName: string;
  packageVersion: string;
  expectedStartedAt: string;
  expectedLogRootPath: string;
  diagnosticOutput: PythonProcessDiagnosticOutput;
}): Promise<ExecutorRunState> {
  try {
    return await waitForExecutorRunStateAvailable({
      filePath: runStatePath,
      processPy,
      getProcessError,
      expectedRunId: runId,
      expectedPackageName: packageName,
      expectedPackageVersion: packageVersion,
      expectedStartedAt,
      expectedLogRootPath,
    });
  } catch (e: unknown) {
    await terminatePythonProcessAfterStartupFailure(processPy, runId);
    logPythonDiagnosticOutput({
      runId,
      reason: getErrorMessage(e),
      diagnosticOutput,
    });
    removeExecutorRunStateFile(runStatePath);
    const strMessage = `Failed to start ${packageName}-${packageVersion}: ${getErrorMessage(e)}`;
    if (processPy.pid === undefined && getProcessError() !== undefined) {
      throw new PythonProcessNotStartedError(strMessage, { cause: e });
    }
    throw new Error(strMessage, { cause: e });
  }
}

async function createRunHistory({
  processPy,
  runId,
  runStatePath,
  runState,
  detail,
  context,
  diagnosticOutput,
}: {
  processPy: ChildProcessWithoutNullStreams;
  runId: string;
  runStatePath: string;
  runState: ExecutorRunState;
  detail: ProjectRunConfig;
  context: RunExecutionContext;
  diagnosticOutput: PythonProcessDiagnosticOutput;
}): Promise<number> {
  try {
    const intRunHistoryIdValue = dbInsertRunHistory({
      schedule_name: detail.schedule_name,
      project_id: detail.local_project_id,
      source: context.source,
      run_id: runId,
      job_id: context.jobId,
      attempt_number: context.attemptNumber,
      snapshot: detail,
      project_name: detail.project_name,
      project_version: detail.project_version,
      python_environment_name: detail.python_environment_name,
      run_started_at_ms: parseExecutorRunTimestamp(runState.startedAt),
      status: RunStatus.Running,
      log_path: runState.logPath,
    }).lastInsertRowid;

    const intRunHistoryId = Number(intRunHistoryIdValue);
    if (!Number.isSafeInteger(intRunHistoryId) || intRunHistoryId <= 0) {
      throw new Error(`Invalid Run History ID: ${String(intRunHistoryIdValue)}`);
    }
    return intRunHistoryId;
  } catch (e: unknown) {
    requestPythonTermination(processPy, runId);
    await waitForPythonProcessTermination(processPy, runId);
    logPythonDiagnosticOutput({
      runId,
      reason: `Failed to create Run History: ${getErrorMessage(e)}`,
      diagnosticOutput,
    });
    removeExecutorRunStateFile(runStatePath);
    throw new Error(`Failed to create Run History: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }
}

function ensureProjectRunMayStart(): void {
  if (boolProjectRunShutdownStarted) {
    throw new Error("Executor is shutting down and cannot start a new Project Run.");
  }
}

async function spawnAndTrackProjectRun(
  detailDict: ProjectRunConfig,
  context: RunExecutionContext,
  runId: string,
): Promise<void> {
  const strExecutorPackagePath =
    context.packagePath ??
    getExecutorPackageFolderPath(detailDict.project_name, detailDict.project_version);

  if (!fs.existsSync(strExecutorPackagePath)) {
    throw new Error(`Installed Project folder does not exist: ${strExecutorPackagePath}`);
  }

  const strPythonEnvironmentPath = getPythonEnvironmentPath(
    detailDict.python_environment_name,
  );
  await validatePackageLiberrpaRequirement(
    strExecutorPackagePath,
    strPythonEnvironmentPath,
  );
  ensureProjectRunMayStart();
  loggerMain.info(
    `Use Python environment '${detailDict.python_environment_name}' for ${detailDict.project_name}-${detailDict.project_version}.`,
  );

  const strProjectLogRootPath = getEffectiveProjectLogFolderPath();
  const strRunStatePath = createExecutorRunStatePath(runId);
  const strStartedAt = new Date().toISOString();
  const floatStartedAt = performance.now();
  // This call already owns one starting slot; all other starts and actual Runs still count.
  context.beforeSpawn?.(hasActiveProjectRun(true), strStartedAt);
  const { processPy, diagnosticOutput, getProcessError } = spawnProjectPythonProcess({
    detail: detailDict,
    packagePath: strExecutorPackagePath,
    pythonEnvironmentPath: strPythonEnvironmentPath,
    runId,
    startedAt: strStartedAt,
    runStatePath: strRunStatePath,
  });
  const activeRun: ActiveProjectRun = {
    processPy,
    runId,
    source: context.source,
    onStopping: context.onStopping,
    forceTerminationRequired: false,
  };
  trackActiveProjectRun(activeRun);

  const dictRunState = await waitForInitialRunState({
    processPy,
    getProcessError,
    runId,
    runStatePath: strRunStatePath,
    packageName: detailDict.project_name,
    packageVersion: detailDict.project_version,
    expectedStartedAt: strStartedAt,
    expectedLogRootPath: strProjectLogRootPath,
    diagnosticOutput,
  });

  loggerMain.debug(`Executor run state is available: ${runId}`);

  const intRunHistoryId = await createRunHistory({
    processPy,
    runId,
    runStatePath: strRunStatePath,
    runState: dictRunState,
    detail: detailDict,
    context,
    diagnosticOutput,
  });

  mapActiveRunByHistoryId.set(intRunHistoryId, activeRun);
  // A Console row is visible only after its actual start has produced local history.
  activeRun.queueItem = {
    queue_id: runId,
    source: context.source,
    schedule_name: detailDict.schedule_name,
    project_name: detailDict.project_name,
    project_version: detailDict.project_version,
    due_at_ms: null,
    started_at_ms: parseExecutorRunTimestamp(dictRunState.startedAt),
    history_id: intRunHistoryId,
    state: JobQueueState.Running,
  };
  mapStartingJobQueueItem.delete(runId);
  const startedFact = {
    runId,
    historyId: intRunHistoryId,
    processId: processPy.pid,
    startedAt: strStartedAt,
    logPath: dictRunState.logPath,
  };
  try {
    context.onStarted?.(startedFact);
  } catch (e: unknown) {
    loggerMain.error(`Failed to persist the actual Run start: ${getErrorMessage(e)}`);
  }

  let timeoutId: NodeJS.Timeout | undefined;
  if (detailDict.timeout_min !== 0) {
    loggerMain.info(`Set timeout: ${String(detailDict.timeout_min)} minute(s).`);
    const stopTimedOutRun = (): void => {
      if (!isProcessRunning(processPy)) return;
      loggerMain.info(
        `Timeout reached. Stop ${detailDict.project_name}-${detailDict.project_version}.`,
      );
      void requestProjectRunTermination(activeRun, RunTerminationReason.Timeout);
    };
    // Startup observation and history creation belong to this Run's timeout budget.
    const floatRemainingMs =
      detailDict.timeout_min * 60 * 1000 - (performance.now() - floatStartedAt);
    if (floatRemainingMs <= 0) stopTimedOutRun();
    else timeoutId = setTimeout(stopTimedOutRun, floatRemainingMs);
  }

  let boolFinalized = false;
  const finalize = (intExitCode: number | null, strSignal: NodeJS.Signals | null): void => {
    if (boolFinalized) {
      return;
    }
    boolFinalized = true;

    loggerMain.info(
      `${detailDict.project_name}-${detailDict.project_version} exited with code ${String(intExitCode)}${
        strSignal === null ? "" : ` and signal ${strSignal}`
      }`,
    );

    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }

    const requestedStatus = getRequestedRunStatus(activeRun.terminationReason);
    let runStatus: RunTerminalStatus = requestedStatus ?? RunStatus.Error;
    let boolUnexpectedProcessFailure =
      getProcessError() !== undefined || activeRun.forceTerminationRequired;
    const intProcessExitedAtMs = Date.now();
    let intRunEndedAtMs = intProcessExitedAtMs;
    let outputs: RunOutputs = {
      status: RunOutputsStatus.Unavailable,
      values: null,
      unavailableKeys: [],
      reason: "Python did not publish a valid final snapshot.",
    };
    let errorSummary: { type: string; message: string } | null = null;

    try {
      const dictFinalState = readExecutorRunState({
        filePath: strRunStatePath,
        expectedRunId: runId,
        expectedPackageName: detailDict.project_name,
        expectedPackageVersion: detailDict.project_version,
        expectedStartedAt: strStartedAt,
        expectedLogRootPath: strProjectLogRootPath,
        expectedLogPath: dictRunState.logPath,
      });
      outputs = dictFinalState.outputs ?? outputs;
      errorSummary = dictFinalState.errorSummary ?? null;
      if (dictFinalState.startedAt !== dictRunState.startedAt) {
        throw new Error(`Final Executor run state changed startedAt for Run ${runId}.`);
      }
      if (dictFinalState.endedAt !== undefined) {
        intRunEndedAtMs = parseExecutorRunTimestamp(dictFinalState.endedAt);
      }

      switch (dictFinalState.status) {
        case ExecutorRunStateStatus.Completed:
          runStatus = RunStatus.Completed;
          break;

        case ExecutorRunStateStatus.Error:
          runStatus = RunStatus.Error;
          break;

        case ExecutorRunStateStatus.Terminated:
          runStatus = requestedStatus ?? RunStatus.Canceled;
          break;

        case ExecutorRunStateStatus.Running:
          loggerMain.error(
            `Python exited before publishing a final Executor run state: ${runId}`,
          );
          runStatus = requestedStatus ?? RunStatus.Error;
          boolUnexpectedProcessFailure = true;
          break;
      }

      const boolUnexpectedExit =
        (intExitCode !== null && intExitCode !== 0) || strSignal !== null;
      if (boolUnexpectedExit) {
        boolUnexpectedProcessFailure = true;
        intRunEndedAtMs = intProcessExitedAtMs;

        if (requestedStatus !== undefined) {
          runStatus = requestedStatus;
        } else {
          if (dictFinalState.status !== ExecutorRunStateStatus.Error) {
            loggerMain.error(
              `Python process ${runId} exited unexpectedly with code ` +
                String(intExitCode) +
                `${strSignal === null ? "" : ` and signal ${strSignal}`}; ` +
                `record Run History status 'interrupted' because the process lifecycle was not completed.`,
            );
          }
          runStatus = RunStatus.Error;
        }
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to read final Executor run state ${runId}: ${getErrorMessage(e)}`,
      );
      runStatus = requestedStatus ?? RunStatus.Error;
      boolUnexpectedProcessFailure = true;
    }

    if (boolUnexpectedProcessFailure) {
      logPythonDiagnosticOutput({
        runId,
        reason:
          "The Python process did not finish through the expected run-state lifecycle.",
        diagnosticOutput,
      });
    }

    if (boolUnexpectedProcessFailure && requestedStatus === undefined)
      runStatus = RunStatus.Interrupted;
    const endedFact: RunEndedFact = {
      ...startedFact,
      endedAt: new Date(intRunEndedAtMs).toISOString(),
      status: runStatus,
      retryEligible: runStatus === RunStatus.Error && !boolUnexpectedProcessFailure,
      outputs,
      errorSummary,
    };
    try {
      getDatabase().transaction(() => {
        dbUpdateRunHistory({
          id: intRunHistoryId,
          run_ended_at_ms: intRunEndedAtMs,
          status: runStatus,
          outputs,
          error_summary: errorSummary,
        });
        context.onEnded?.(endedFact);
      })();
      removeExecutorRunStateFile(strRunStatePath);
      notifyRunFinished(detailDict, context, endedFact);
    } catch (e: unknown) {
      loggerMain.error(`Failed to persist the actual Run result: ${getErrorMessage(e)}`);
    } finally {
      mapActiveRunByHistoryId.delete(intRunHistoryId);
      notifyRunEnded();
    }
  };

  processPy.once("close", finalize);

  // The process may have exited after the initial state was read but before the listener was registered.
  if (processPy.exitCode !== null || processPy.signalCode !== null) {
    finalize(processPy.exitCode, processPy.signalCode);
  }
}

export async function startProjectRun(
  detailDict: ProjectRunConfig,
  context: RunExecutionContext = {
    source: RunSource.Local,
    jobId: randomUUID(),
    attemptNumber: 1,
  },
): Promise<void> {
  // Scheduled and manual launches wait without dropping work while a Console account change commits.
  if (promiseConsoleAccountTransition !== undefined) {
    await promiseConsoleAccountTransition;
  }

  ensureProjectRunMayStart();

  const strRunId = context.runId ?? randomUUID();
  if (context.source === RunSource.Local) {
    mapStartingJobQueueItem.set(strRunId, {
      queue_id: strRunId,
      source: RunSource.Local,
      schedule_name: detailDict.schedule_name,
      project_name: detailDict.project_name,
      project_version: detailDict.project_version,
      due_at_ms: null,
      started_at_ms: null,
      history_id: null,
      state: JobQueueState.Starting,
    });
  }
  mapStartingRun.set(strRunId, {
    localProjectId: detailDict.local_project_id,
    source: context.source,
  });
  notifyRunActivityChanged();
  const promiseStartingRun = spawnAndTrackProjectRun(
    structuredClone(detailDict),
    context,
    strRunId,
  );
  setStartingRunPromise.add(promiseStartingRun);
  try {
    await promiseStartingRun;
  } finally {
    setStartingRunPromise.delete(promiseStartingRun);
    mapStartingJobQueueItem.delete(strRunId);
    mapStartingRun.delete(strRunId);
    notifyRunActivityChanged();
  }
}

export function cancelRunByHistoryId(runHistoryId: number): void {
  const activeRun = mapActiveRunByHistoryId.get(runHistoryId);
  if (activeRun === undefined) {
    loggerMain.debug(
      `No running Python process is cached for Run History ${String(runHistoryId)}.`,
    );
    return;
  }

  if (!isProcessRunning(activeRun.processPy)) {
    loggerMain.debug(
      `Python process for Run History ${String(runHistoryId)} is already closing.`,
    );
    return;
  }

  loggerMain.info(`Cancel Run History ${String(runHistoryId)}.`);
  void requestProjectRunTermination(activeRun, RunTerminationReason.Cancel);
}

export function cancelRunById(runId: string): void {
  const activeRun = mapActiveRunByRunId.get(runId);
  if (activeRun) void requestProjectRunTermination(activeRun, RunTerminationReason.Cancel);
}

export function beginProjectRunShutdown(): void {
  boolProjectRunShutdownStarted = true;
}

export async function shutdownProjectRuns(): Promise<void> {
  beginProjectRunShutdown();

  const arrStartingRunPromise = [...setStartingRunPromise];
  if (arrStartingRunPromise.length !== 0) {
    loggerMain.info(
      `Wait for ${String(arrStartingRunPromise.length)} starting Project Run(s) before Executor exits.`,
    );
    await Promise.allSettled(arrStartingRunPromise);
  }

  const arrActiveRun = [...mapActiveRunByRunId.values()];
  if (arrActiveRun.length !== 0) {
    loggerMain.info(
      `Stop ${String(arrActiveRun.length)} active Project Run(s) before Executor exits.`,
    );
    await Promise.all(
      arrActiveRun.map((activeRun) =>
        requestProjectRunTermination(activeRun, RunTerminationReason.Shutdown),
      ),
    );
  }
}
