// FileName: projectRunner.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs";

import { getErrorMessage } from "../../shared/error";
import {
  type RunOutputs,
  type RunTerminalStatus,
  type RunQueueItem,
  RunQueueState,
  RunSource,
  RunStatus,
} from "../../shared/run";
import { isProcessRunning } from "../Common/process";
import { getEffectiveProjectLogFolderPath } from "../Config/executorConfig";
import { getPythonEnvironmentPath } from "../Config/environment";
import { dbInsertRunHistory, dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { getDatabase } from "../Database/connection";
import { validatePythonPackageEnvironment } from "../Package/packageMetadata";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { notifyRunEnded, notifyRunActivityChanged, notifyRunFinished } from "./lifecycle";
import {
  type PythonProcessDiagnosticOutput,
  logPythonDiagnosticOutput,
  requestPythonTermination,
  spawnProjectPythonProcess,
  terminatePythonProcessAfterStartupFailure,
  waitForPythonProcessTermination,
} from "./pythonProcess";
import {
  type ExecutorRunState,
  createExecutorRunStatePath,
  parseExecutorRunTimestamp,
  readExecutorRunState,
  removeExecutorRunStateFile,
  waitForExecutorRunStateAvailable,
} from "./runState";
import {
  type ProjectRunDetails,
  type RunExecutionContext,
  type RunEndedFact,
  RunTerminationReason,
} from "./types";
import { hasRecoveredRun } from "./recoveredRuns";

interface ActiveProjectRun {
  processPy: ChildProcessWithoutNullStreams;
  strRunId: string;
  source: RunSource;
  queueItem?: RunQueueItem;
  onStopping?: RunExecutionContext["onStopping"];
  terminationReason?: RunTerminationReason;
  terminationPromise?: Promise<void>;
  boolForceTerminationRequired: boolean;
}

const mapActiveRunByHistoryId = new Map<number, ActiveProjectRun>();
const mapActiveRunByRunId = new Map<string, ActiveProjectRun>();
const mapStartingRunQueueItem = new Map<string, RunQueueItem>();

const mapStartingRunCountByProject = new Map<number, number>();
const setStartingRunPromise = new Set<Promise<void>>();
let intStartingRunCount = 0;
let intStartingLocalRunCount = 0;
let boolProjectRunShutdownStarted = false;
let promiseConsoleAccountTransition: Promise<void> | undefined;
let finishConsoleAccountTransition: (() => void) | undefined;

export function hasActiveProjectRun(excludeCurrentStart = false): boolean {
  return (
    intStartingRunCount > (excludeCurrentStart ? 1 : 0) ||
    mapActiveRunByRunId.size !== 0 ||
    hasRecoveredRun()
  );
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

function addStartingRun(projectId: number, source: RunSource): void {
  intStartingRunCount += 1;
  if (source === RunSource.Local) intStartingLocalRunCount += 1;
  mapStartingRunCountByProject.set(
    projectId,
    (mapStartingRunCountByProject.get(projectId) ?? 0) + 1,
  );
  notifyRunActivityChanged();
}

function removeStartingRun(projectId: number, source: RunSource): void {
  intStartingRunCount -= 1;
  if (source === RunSource.Local) intStartingLocalRunCount -= 1;
  const intProjectCount = mapStartingRunCountByProject.get(projectId);
  if (intProjectCount === undefined || intProjectCount <= 1) {
    mapStartingRunCountByProject.delete(projectId);
  } else {
    mapStartingRunCountByProject.set(projectId, intProjectCount - 1);
  }
  notifyRunActivityChanged();
}

function trackActiveProjectRun(activeRun: ActiveProjectRun): void {
  mapActiveRunByRunId.set(activeRun.strRunId, activeRun);
  activeRun.processPy.once("close", () => {
    if (mapActiveRunByRunId.get(activeRun.strRunId) === activeRun) {
      mapActiveRunByRunId.delete(activeRun.strRunId);
      notifyRunActivityChanged();
    }
  });
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
  if (!requestPythonTermination(activeRun.processPy, activeRun.strRunId)) {
    loggerMain.debug(
      `Python process ${activeRun.strRunId} cannot receive the termination message.`,
    );
  }

  const promiseTermination = waitForPythonProcessTermination(
    activeRun.processPy,
    activeRun.strRunId,
    () => {
      activeRun.boolForceTerminationRequired = true;
    },
  );
  activeRun.terminationPromise = promiseTermination;
  notifyRunActivityChanged();
  return promiseTermination;
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

export function beginProjectRunShutdown(): void {
  boolProjectRunShutdownStarted = true;
}

export async function shutdownProjectRuns(): Promise<void> {
  beginProjectRunShutdown();

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

  const arrStartingRunPromise = [...setStartingRunPromise];
  if (arrStartingRunPromise.length !== 0) {
    loggerMain.info(
      `Wait for ${String(arrStartingRunPromise.length)} starting Project Run(s) before Executor exits.`,
    );
    await Promise.allSettled(arrStartingRunPromise);
  }
}

export function isProjectRunStarting(projectId: number): boolean {
  return mapStartingRunCountByProject.has(projectId);
}

export async function pythonRun(
  detailDict: ProjectRunDetails,
  context: RunExecutionContext = {
    source: RunSource.Local,
    jobId: randomUUID(),
    attempt: 1,
  },
): Promise<void> {
  // Scheduled and manual launches wait without dropping work while a Console account change commits.
  if (promiseConsoleAccountTransition !== undefined) {
    await promiseConsoleAccountTransition;
  }

  if (boolProjectRunShutdownStarted) {
    throw new Error("Executor is shutting down and cannot start a new Project Run.");
  }

  const strRunId = context.runId ?? randomUUID();
  if (context.source === RunSource.Local) {
    mapStartingRunQueueItem.set(strRunId, {
      queue_id: strRunId,
      source: RunSource.Local,
      schedule_name: detailDict.schedule_name,
      project_name: detailDict.name,
      project_version: detailDict.version,
      estimated_run_at_ms: null,
      started_at_ms: null,
      history_id: null,
      state: RunQueueState.Starting,
    });
  }
  addStartingRun(detailDict.id, context.source);
  const promiseStartingRun = startProjectRun(
    structuredClone(detailDict),
    context,
    strRunId,
  );
  setStartingRunPromise.add(promiseStartingRun);
  try {
    await promiseStartingRun;
  } finally {
    setStartingRunPromise.delete(promiseStartingRun);
    mapStartingRunQueueItem.delete(strRunId);
    removeStartingRun(detailDict.id, context.source);
  }
}

async function startProjectRun(
  detailDict: ProjectRunDetails,
  context: RunExecutionContext,
  runId: string,
): Promise<void> {
  const strExecutorPackagePath =
    context.packagePath ??
    getExecutorPackageFolderPath(detailDict.name, detailDict.version);

  if (!fs.existsSync(strExecutorPackagePath)) {
    throw new Error(`Installed Project folder does not exist: ${strExecutorPackagePath}`);
  }

  const strPythonEnvironmentPath = getPythonEnvironmentPath(
    detailDict.python_environment_name,
  );
  await validatePythonPackageEnvironment(strExecutorPackagePath, strPythonEnvironmentPath);
  loggerMain.info(
    `Use Python environment '${detailDict.python_environment_name}' for ${detailDict.name}-${detailDict.version}.`,
  );

  const strProjectLogRootPath = getEffectiveProjectLogFolderPath();
  const strRunStatePath = createExecutorRunStatePath(runId);
  const strStartedAt = new Date().toISOString();
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
    strRunId: runId,
    source: context.source,
    onStopping: context.onStopping,
    boolForceTerminationRequired: false,
  };
  trackActiveProjectRun(activeRun);

  const dictRunState = await getInitialRunState({
    processPy,
    getProcessError,
    runId,
    runStatePath: strRunStatePath,
    packageName: detailDict.name,
    packageVersion: detailDict.version,
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
    project_name: detailDict.name,
    project_version: detailDict.version,
    estimated_run_at_ms: null,
    started_at_ms: parseExecutorRunTimestamp(dictRunState.startedAt),
    history_id: intRunHistoryId,
    state: RunQueueState.Running,
  };
  mapStartingRunQueueItem.delete(runId);
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
    timeoutId = setTimeout(
      () => {
        if (!isProcessRunning(processPy)) {
          return;
        }

        loggerMain.info(`Timeout reached. Stop ${detailDict.name}-${detailDict.version}.`);
        void requestProjectRunTermination(activeRun, RunTerminationReason.Timeout);
      },
      detailDict.timeout_min * 60 * 1000,
    );
  }

  let boolFinalized = false;
  const finalize = (intExitCode: number | null, strSignal: NodeJS.Signals | null): void => {
    if (boolFinalized) {
      return;
    }
    boolFinalized = true;

    loggerMain.info(
      `${detailDict.name}-${detailDict.version} exited with code ${String(intExitCode)}${
        strSignal === null ? "" : ` and signal ${strSignal}`
      }`,
    );

    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }

    const requestedStatus = getRequestedRunStatus(activeRun.terminationReason);
    let runStatus: RunTerminalStatus = requestedStatus ?? RunStatus.Error;
    let boolUnexpectedProcessFailure =
      getProcessError() !== undefined || activeRun.boolForceTerminationRequired;
    const intProcessExitedAtMs = Date.now();
    let intRunEndedAtMs = intProcessExitedAtMs;
    let outputs: RunOutputs = {
      status: "unavailable",
      values: null,
      unavailableKeys: [],
      reason: "Python did not publish a valid final snapshot.",
    };
    let errorSummary: { type: string; message: string } | null = null;

    try {
      const dictFinalState = readExecutorRunState({
        filePath: strRunStatePath,
        expectedRunId: runId,
        expectedPackageName: detailDict.name,
        expectedPackageVersion: detailDict.version,
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
        case "completed":
          runStatus = RunStatus.Completed;
          break;

        case "error":
          runStatus = RunStatus.Error;
          break;

        case "terminated":
          runStatus = requestedStatus ?? RunStatus.Canceled;
          break;

        case "running":
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
          if (dictFinalState.status !== "error") {
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

async function getInitialRunState({
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
    throw new Error(
      `Failed to start ${packageName}-${packageVersion}: ${getErrorMessage(e)}`,
      { cause: e },
    );
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
  detail: ProjectRunDetails;
  context: RunExecutionContext;
  diagnosticOutput: PythonProcessDiagnosticOutput;
}): Promise<number> {
  try {
    const intRunHistoryIdValue = dbInsertRunHistory({
      schedule_name: detail.schedule_name,
      project_id: context.source === RunSource.Console ? null : detail.id,
      source: context.source,
      console_url:
        context.source === RunSource.Console ? (context.consoleUrl ?? null) : null,
      run_id: runId,
      job_id: context.jobId,
      attempt: context.attempt,
      inputs: detail,
      project_name: detail.name,
      project_version: detail.version,
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

export function pythonCancel(runHistoryId: number): void {
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

export function getActiveRunQueueItems(): RunQueueItem[] {
  const arrItem = [...mapStartingRunQueueItem.values()].map((item) => ({ ...item }));
  for (const activeRun of mapActiveRunByRunId.values()) {
    if (activeRun.queueItem === undefined) continue;
    arrItem.push({
      ...activeRun.queueItem,
      state:
        activeRun.terminationReason === undefined
          ? RunQueueState.Running
          : RunQueueState.Stopping,
    });
  }
  return arrItem;
}

export function getActiveConsoleRunIds(): string[] {
  return [...mapActiveRunByRunId.values()]
    .filter((activeRun) => activeRun.source === RunSource.Console)
    .map((activeRun) => activeRun.strRunId);
}

export function cancelRunById(runId: string): void {
  const activeRun = mapActiveRunByRunId.get(runId);
  if (activeRun) void requestProjectRunTermination(activeRun, RunTerminationReason.Cancel);
}

export function getLocalRunningCount(): number {
  return (
    [...mapActiveRunByRunId.values()].filter(
      (activeRun) => activeRun.source === RunSource.Local,
    ).length + intStartingLocalRunCount
  );
}
