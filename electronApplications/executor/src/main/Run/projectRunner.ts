// FileName: projectRunner.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs";

import { getErrorMessage } from "../../shared/error";
import { isProcessRunning } from "../Common/process";
import { getEffectiveProjectLogFolderPath } from "../Config/executorConfig";
import { getPythonEnvironmentPath } from "../Config/environment";
import { dbInsertRunHistory, dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { notifyRunEnded } from "./lifecycle";
import {
  type Dict_PythonProcess_DiagnosticOutput,
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
import type { Dict_ProjectRun_Detail } from "./types";

type Str_ProjectRunTerminationReason = "cancel" | "shutdown" | "timeout";
type Str_RunHistoryTerminalStatus = "cancel" | "completed" | "error" | "timeout";

interface ActiveProjectRun {
  processPy: ChildProcessWithoutNullStreams;
  strRunId: string;
  terminationReason?: Str_ProjectRunTerminationReason;
  terminationPromise?: Promise<void>;
  boolForceTerminationRequired: boolean;
}

const mapActiveRunByHistoryId = new Map<number, ActiveProjectRun>();
const mapActiveRunByRunId = new Map<string, ActiveProjectRun>();

const mapStartingRunCountByProject = new Map<number, number>();
const setStartingRunPromise = new Set<Promise<void>>();
let intStartingRunCount = 0;
let boolProjectRunShutdownStarted = false;

function addStartingRun(projectId: number): void {
  intStartingRunCount += 1;
  mapStartingRunCountByProject.set(
    projectId,
    (mapStartingRunCountByProject.get(projectId) ?? 0) + 1,
  );
}

function removeStartingRun(projectId: number): void {
  intStartingRunCount -= 1;
  const intProjectCount = mapStartingRunCountByProject.get(projectId);
  if (intProjectCount === undefined || intProjectCount <= 1) {
    mapStartingRunCountByProject.delete(projectId);
  } else {
    mapStartingRunCountByProject.set(projectId, intProjectCount - 1);
  }
}

function trackActiveProjectRun(activeRun: ActiveProjectRun): void {
  mapActiveRunByRunId.set(activeRun.strRunId, activeRun);
  activeRun.processPy.once("close", () => {
    if (mapActiveRunByRunId.get(activeRun.strRunId) === activeRun) {
      mapActiveRunByRunId.delete(activeRun.strRunId);
    }
  });
}

function requestProjectRunTermination(
  activeRun: ActiveProjectRun,
  reason: Str_ProjectRunTerminationReason,
): Promise<void> {
  if (activeRun.terminationPromise !== undefined) {
    return activeRun.terminationPromise;
  }
  if (!isProcessRunning(activeRun.processPy)) {
    return Promise.resolve();
  }

  activeRun.terminationReason = reason;
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
  return promiseTermination;
}

function getRequestedRunHistoryStatus(
  terminationReason: Str_ProjectRunTerminationReason | undefined,
): "cancel" | "timeout" | undefined {
  if (terminationReason === "timeout") {
    return "timeout";
  }
  if (terminationReason !== undefined) {
    return "cancel";
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
      arrActiveRun.map((activeRun) => requestProjectRunTermination(activeRun, "shutdown")),
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

export function hasStartingRun(): boolean {
  return intStartingRunCount !== 0;
}

export function isProjectRunStarting(projectId: number): boolean {
  return mapStartingRunCountByProject.has(projectId);
}

export async function pythonRun(detailDict: Dict_ProjectRun_Detail): Promise<void> {
  if (boolProjectRunShutdownStarted) {
    throw new Error("Executor is shutting down and cannot start a new Project Run.");
  }

  addStartingRun(detailDict.id);
  const promiseStartingRun = startProjectRun(detailDict);
  setStartingRunPromise.add(promiseStartingRun);
  try {
    await promiseStartingRun;
  } finally {
    setStartingRunPromise.delete(promiseStartingRun);
    removeStartingRun(detailDict.id);
  }
}

async function startProjectRun(detailDict: Dict_ProjectRun_Detail): Promise<void> {
  const strExecutorPackagePath = getExecutorPackageFolderPath(
    detailDict.name,
    detailDict.version,
  );

  if (!fs.existsSync(strExecutorPackagePath)) {
    throw new Error(`Installed Project folder does not exist: ${strExecutorPackagePath}`);
  }

  const strPythonEnvironmentPath = getPythonEnvironmentPath(
    detailDict.python_environment_name,
  );
  loggerMain.info(
    `Use Python environment '${detailDict.python_environment_name}' for ${detailDict.name}-${detailDict.version}.`,
  );

  const strRunId = randomUUID();
  const strStartedAt = new Date().toISOString();
  const strProjectLogRootPath = getEffectiveProjectLogFolderPath();
  const strRunStatePath = createExecutorRunStatePath(strRunId);
  const { processPy, diagnosticOutput, getProcessError } = spawnProjectPythonProcess({
    detail: detailDict,
    packagePath: strExecutorPackagePath,
    pythonEnvironmentPath: strPythonEnvironmentPath,
    runId: strRunId,
    startedAt: strStartedAt,
    runStatePath: strRunStatePath,
  });
  const activeRun: ActiveProjectRun = {
    processPy,
    strRunId,
    boolForceTerminationRequired: false,
  };
  trackActiveProjectRun(activeRun);

  const dictRunState = await getInitialRunState({
    processPy,
    getProcessError,
    runId: strRunId,
    runStatePath: strRunStatePath,
    packageName: detailDict.name,
    packageVersion: detailDict.version,
    expectedStartedAt: strStartedAt,
    expectedLogRootPath: strProjectLogRootPath,
    diagnosticOutput,
  });

  loggerMain.debug(`Executor run state is available: ${strRunId}`);

  const intRunHistoryId = await createRunHistory({
    processPy,
    runId: strRunId,
    runStatePath: strRunStatePath,
    runState: dictRunState,
    detail: detailDict,
    diagnosticOutput,
  });

  mapActiveRunByHistoryId.set(intRunHistoryId, activeRun);

  let timeoutId: NodeJS.Timeout | undefined;
  if (detailDict.timeout_min !== 0) {
    loggerMain.info(`Set timeout: ${String(detailDict.timeout_min)} minute(s).`);
    timeoutId = setTimeout(
      () => {
        if (!isProcessRunning(processPy)) {
          return;
        }

        loggerMain.info(`Timeout reached. Stop ${detailDict.name}-${detailDict.version}.`);
        void requestProjectRunTermination(activeRun, "timeout");
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

    const strRequestedStatus = getRequestedRunHistoryStatus(activeRun.terminationReason);
    let strRunHistoryStatus: Str_RunHistoryTerminalStatus = strRequestedStatus ?? "error";
    let boolUnexpectedProcessFailure =
      getProcessError() !== undefined || activeRun.boolForceTerminationRequired;
    const intProcessExitedAtMs = Date.now();
    let intRunEndedAtMs = intProcessExitedAtMs;

    try {
      const dictFinalState = readExecutorRunState({
        filePath: strRunStatePath,
        expectedRunId: strRunId,
        expectedPackageName: detailDict.name,
        expectedPackageVersion: detailDict.version,
        expectedStartedAt: strStartedAt,
        expectedLogRootPath: strProjectLogRootPath,
        expectedLogPath: dictRunState.logPath,
      });
      if (dictFinalState.startedAt !== dictRunState.startedAt) {
        throw new Error(`Final Executor run state changed startedAt for Run ${strRunId}.`);
      }
      if (dictFinalState.endedAt !== undefined) {
        intRunEndedAtMs = parseExecutorRunTimestamp(dictFinalState.endedAt);
      }

      switch (dictFinalState.status) {
        case "completed":
          strRunHistoryStatus = "completed";
          break;

        case "error":
          strRunHistoryStatus = "error";
          break;

        case "terminated":
          strRunHistoryStatus = strRequestedStatus ?? "cancel";
          break;

        case "running":
          loggerMain.error(
            `Python exited before publishing a final Executor run state: ${strRunId}`,
          );
          strRunHistoryStatus = strRequestedStatus ?? "error";
          boolUnexpectedProcessFailure = true;
          break;
      }

      const boolUnexpectedExit =
        (intExitCode !== null && intExitCode !== 0) || strSignal !== null;
      if (boolUnexpectedExit) {
        boolUnexpectedProcessFailure = true;
        intRunEndedAtMs = intProcessExitedAtMs;

        if (strRequestedStatus !== undefined) {
          strRunHistoryStatus = strRequestedStatus;
        } else {
          if (dictFinalState.status !== "error") {
            loggerMain.error(
              `Python process ${strRunId} exited unexpectedly with code ${String(intExitCode)}` +
                `${strSignal === null ? "" : ` and signal ${strSignal}`}; ` +
                `override final Run State '${dictFinalState.status}' with Run History status 'error'.`,
            );
          }
          strRunHistoryStatus = "error";
        }
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to read final Executor run state ${strRunId}: ${getErrorMessage(e)}`,
      );
      strRunHistoryStatus = strRequestedStatus ?? "error";
      boolUnexpectedProcessFailure = true;
    }

    if (boolUnexpectedProcessFailure) {
      logPythonDiagnosticOutput({
        runId: strRunId,
        reason:
          "The Python process did not finish through the expected run-state lifecycle.",
        diagnosticOutput,
      });
    }

    try {
      dbUpdateRunHistory({
        id: intRunHistoryId,
        run_ended_at_ms: intRunEndedAtMs,
        status: strRunHistoryStatus,
      });
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to update Run History ${String(intRunHistoryId)}: ${getErrorMessage(e)}`,
      );
    } finally {
      mapActiveRunByHistoryId.delete(intRunHistoryId);
      removeExecutorRunStateFile(strRunStatePath);
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
  diagnosticOutput: Dict_PythonProcess_DiagnosticOutput;
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
  diagnosticOutput,
}: {
  processPy: ChildProcessWithoutNullStreams;
  runId: string;
  runStatePath: string;
  runState: ExecutorRunState;
  detail: Dict_ProjectRun_Detail;
  diagnosticOutput: Dict_PythonProcess_DiagnosticOutput;
}): Promise<number> {
  try {
    const intRunHistoryIdValue = dbInsertRunHistory({
      schedule_name: detail.schedule_name,
      project_id: detail.id,
      project_name: detail.name,
      project_version: detail.version,
      python_environment_name: detail.python_environment_name,
      run_started_at_ms: parseExecutorRunTimestamp(runState.startedAt),
      status: "running",
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
  void requestProjectRunTermination(activeRun, "cancel");
}
