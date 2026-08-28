// FileName: projectRunner.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs";

import { getEffectiveProjectLogFolderPath } from "../Config/executorConfig";
import { getPythonEnvironmentPath } from "../Config/environment";
import { dbInsertRunHistory, dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import type { Dict_ProjectRun_Detail } from "./types";
import { notifyRunEnded } from "./lifecycle";
import {
  type Dict_PythonProcess_DiagnosticOutput,
  isPythonProcessRunning,
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

type Str_RunHistoryTerminalStatus = "cancel" | "completed" | "error" | "timeout";

interface RunningPythonProcess {
  processPy: ChildProcessWithoutNullStreams;
  strRunId: string;
}

const mapProcessCache = new Map<number, RunningPythonProcess>();
const mapActiveProcessByRunId = new Map<string, ChildProcessWithoutNullStreams>();

const mapStartingRunCountByProject = new Map<number, number>();
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

function trackActiveProjectProcess(
  processPy: ChildProcessWithoutNullStreams,
  runId: string,
): void {
  mapActiveProcessByRunId.set(runId, processPy);
  processPy.once("close", () => {
    if (mapActiveProcessByRunId.get(runId) === processPy) {
      mapActiveProcessByRunId.delete(runId);
    }
  });
}

export function beginProjectRunShutdown(): void {
  boolProjectRunShutdownStarted = true;
}

export async function shutdownProjectRuns(): Promise<void> {
  beginProjectRunShutdown();

  const arrProcess = [...mapActiveProcessByRunId.entries()];
  if (arrProcess.length === 0) {
    return;
  }

  loggerMain.info(`Stop ${arrProcess.length} active Project Run(s) before Executor exits.`);
  await Promise.all(
    arrProcess.map(async ([strRunId, processPy]) => {
      requestPythonTermination(processPy, strRunId);
      await waitForPythonProcessTermination(processPy, strRunId);
    }),
  );
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
  try {
    await startProjectRun(detailDict);
  } finally {
    removeStartingRun(detailDict.id);
  }
}

async function startProjectRun(detailDict: Dict_ProjectRun_Detail): Promise<void> {
  // Only the local source is supported now.
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
  trackActiveProjectProcess(processPy, strRunId);

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
    logRootPath: strProjectLogRootPath,
    detail: detailDict,
    diagnosticOutput,
  });

  mapProcessCache.set(intRunHistoryId, { processPy, strRunId });

  let boolTimeout = false;
  let timeoutId: NodeJS.Timeout | undefined;
  if (detailDict.timeout_min !== 0) {
    loggerMain.info(`Set timeout: ${detailDict.timeout_min}`);
    timeoutId = setTimeout(
      () => {
        if (!isPythonProcessRunning(processPy)) {
          return;
        }

        loggerMain.info(
          `Timeout reached. Stopping ${detailDict.name}-${detailDict.version}`,
        );
        boolTimeout = requestPythonTermination(processPy, strRunId);
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

    let strRunHistoryStatus: Str_RunHistoryTerminalStatus = "error";
    let boolUnexpectedProcessFailure = getProcessError() !== undefined;
    let intRunEndedAtMs = Date.now();

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
          strRunHistoryStatus = boolTimeout ? "timeout" : "cancel";
          break;

        case "running":
          loggerMain.error(
            `Python exited before publishing a final Executor run state: ${strRunId}`,
          );
          strRunHistoryStatus = "error";
          boolUnexpectedProcessFailure = true;
          break;
      }

      if (
        dictFinalState.status !== "terminated" &&
        ((intExitCode !== null && intExitCode !== 0) || strSignal !== null)
      ) {
        boolUnexpectedProcessFailure = true;
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to read final Executor run state ${strRunId}: ${getErrorMessage(e)}`,
      );
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
        `Failed to update Run History ${intRunHistoryId}: ${getErrorMessage(e)}`,
      );
    } finally {
      mapProcessCache.delete(intRunHistoryId);
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
  logRootPath,
  detail,
  diagnosticOutput,
}: {
  processPy: ChildProcessWithoutNullStreams;
  runId: string;
  runStatePath: string;
  runState: ExecutorRunState;
  logRootPath: string;
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
      log_root_path: logRootPath,
    }).lastInsertRowid;

    const intRunHistoryId = Number(intRunHistoryIdValue);
    if (!Number.isSafeInteger(intRunHistoryId)) {
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

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}

export function pythonCancel(runHistoryId: number): void {
  const runningProcess = mapProcessCache.get(runHistoryId);
  if (runningProcess !== undefined) {
    if (!requestPythonTermination(runningProcess.processPy, runningProcess.strRunId)) {
      loggerMain.debug(
        `Python process for Run History ${runHistoryId} is already closing.`,
      );
    }
    return;
  }

  loggerMain.debug(`No running Python process is cached for Run History ${runHistoryId}.`);
}
