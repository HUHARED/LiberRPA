import type { ChildProcessWithoutNullStreams } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs";

import { getPythonEnvironmentPath } from "../Config/environment";
import {
  dbInsertHistoryDetail,
  dbUpdateHistoryDetail,
} from "../Database/historyRepository";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import type { DictColumns_Project_Detail_Run } from "../../shared/interface";
import { notifyRunEnded } from "./lifecycle";
import {
  type DictPythonProcessDiagnosticOutput,
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

type ExecutorHistoryStatus = "cancel" | "completed" | "error" | "timeout";

interface RunningPythonProcess {
  processPy: ChildProcessWithoutNullStreams;
  strRunId: string;
}

const mapProcessCache = new Map<number, RunningPythonProcess>();

export async function pythonRun(dictDetail: DictColumns_Project_Detail_Run): Promise<void> {
  // Only the local source is supported now.
  const strExecutorPackagePath = getExecutorPackageFolderPath(
    dictDetail.name,
    dictDetail.version,
  );

  if (!fs.existsSync(strExecutorPackagePath)) {
    throw new Error(`Installed Project folder does not exist: ${strExecutorPackagePath}`);
  }

  const strPythonEnvironmentPath = getPythonEnvironmentPath(
    dictDetail.python_environment_name,
  );
  loggerMain.info(
    `Use Python environment '${dictDetail.python_environment_name}' for ${dictDetail.name}-${dictDetail.version}.`,
  );

  const strRunId = randomUUID();
  const strStartedAt = new Date().toISOString();
  const strRunStatePath = createExecutorRunStatePath(strRunId);
  const { processPy, diagnosticOutput, getProcessError } = spawnProjectPythonProcess({
    detail: dictDetail,
    packagePath: strExecutorPackagePath,
    pythonEnvironmentPath: strPythonEnvironmentPath,
    runId: strRunId,
    startedAt: strStartedAt,
    runStatePath: strRunStatePath,
  });

  const dictRunState = await getInitialRunState({
    processPy,
    getProcessError,
    runId: strRunId,
    runStatePath: strRunStatePath,
    packageName: dictDetail.name,
    packageVersion: dictDetail.version,
    diagnosticOutput,
  });

  loggerMain.debug(`Executor run state is available: ${strRunId}`);

  const intHistoryId = await createTaskHistory({
    processPy,
    runId: strRunId,
    runStatePath: strRunStatePath,
    runState: dictRunState,
    detail: dictDetail,
    diagnosticOutput,
  });

  mapProcessCache.set(intHistoryId, { processPy, strRunId });

  let boolTimeout = false;
  let timeoutId: NodeJS.Timeout | undefined;
  if (dictDetail.timeout_min !== 0) {
    loggerMain.info(`Set timeout: ${dictDetail.timeout_min}`);
    timeoutId = setTimeout(
      () => {
        if (!isPythonProcessRunning(processPy)) {
          return;
        }

        loggerMain.info(
          `Timeout reached. Stopping ${dictDetail.name}-${dictDetail.version}`,
        );
        boolTimeout = requestPythonTermination(processPy, strRunId);
      },
      dictDetail.timeout_min * 60 * 1000,
    );
  }

  let boolFinalized = false;
  const finalize = (intExitCode: number | null, strSignal: NodeJS.Signals | null): void => {
    if (boolFinalized) {
      return;
    }
    boolFinalized = true;

    loggerMain.info(
      `${dictDetail.name}-${dictDetail.version} exited with code ${String(intExitCode)}${
        strSignal === null ? "" : ` and signal ${strSignal}`
      }`,
    );

    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }

    let strHistoryStatus: ExecutorHistoryStatus = "error";
    let boolUnexpectedProcessFailure = getProcessError() !== undefined;
    let intRunEndedAtMs = Date.now();

    try {
      const dictFinalState = readExecutorRunState({
        filePath: strRunStatePath,
        expectedRunId: strRunId,
        expectedPackageName: dictDetail.name,
        expectedPackageVersion: dictDetail.version,
      });
      if (dictFinalState.endedAt !== undefined) {
        intRunEndedAtMs = parseExecutorRunTimestamp(dictFinalState.endedAt);
      }

      switch (dictFinalState.status) {
        case "completed":
          strHistoryStatus = "completed";
          break;

        case "error":
          strHistoryStatus = "error";
          break;

        case "terminated":
          strHistoryStatus = boolTimeout ? "timeout" : "cancel";
          break;

        case "running":
          loggerMain.error(
            `Python exited before publishing a final Executor run state: ${strRunId}`,
          );
          strHistoryStatus = "error";
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
      dbUpdateHistoryDetail({
        id: intHistoryId,
        run_ended_at_ms: intRunEndedAtMs,
        status: strHistoryStatus,
      });
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to update Task History ${intHistoryId}: ${getErrorMessage(e)}`,
      );
    } finally {
      mapProcessCache.delete(intHistoryId);
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
  diagnosticOutput,
}: {
  processPy: ChildProcessWithoutNullStreams;
  getProcessError: () => Error | undefined;
  runId: string;
  runStatePath: string;
  packageName: string;
  packageVersion: string;
  diagnosticOutput: DictPythonProcessDiagnosticOutput;
}): Promise<ExecutorRunState> {
  try {
    return await waitForExecutorRunStateAvailable({
      filePath: runStatePath,
      processPy,
      getProcessError,
      expectedRunId: runId,
      expectedPackageName: packageName,
      expectedPackageVersion: packageVersion,
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

async function createTaskHistory({
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
  detail: DictColumns_Project_Detail_Run;
  diagnosticOutput: DictPythonProcessDiagnosticOutput;
}): Promise<number> {
  try {
    const intHistoryIdValue = dbInsertHistoryDetail({
      scheduler_name: detail.scheduler_name,
      project_source: detail.project_source,
      project_id: detail.id,
      project_name: detail.name,
      project_version: detail.version,
      python_environment_name: detail.python_environment_name,
      run_started_at_ms: parseExecutorRunTimestamp(runState.startedAt),
      status: "running",
      log_path: runState.logPath,
    }).lastInsertRowid;

    const intHistoryId = Number(intHistoryIdValue);
    if (!Number.isSafeInteger(intHistoryId)) {
      throw new Error(`Invalid Task History ID: ${String(intHistoryIdValue)}`);
    }
    return intHistoryId;
  } catch (e: unknown) {
    requestPythonTermination(processPy, runId);
    await waitForPythonProcessTermination(processPy, runId);
    logPythonDiagnosticOutput({
      runId,
      reason: `Failed to create Task History: ${getErrorMessage(e)}`,
      diagnosticOutput,
    });
    removeExecutorRunStateFile(runStatePath);
    throw new Error(`Failed to create Task History: ${getErrorMessage(e)}`, {
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

export function pythonCancel(historyId: number): void {
  const runningProcess = mapProcessCache.get(historyId);
  if (runningProcess !== undefined) {
    if (!requestPythonTermination(runningProcess.processPy, runningProcess.strRunId)) {
      loggerMain.debug(`Python process for Task History ${historyId} is already closing.`);
    }
    return;
  }

  loggerMain.debug(`No running Python process is cached for Task History ${historyId}.`);
}
