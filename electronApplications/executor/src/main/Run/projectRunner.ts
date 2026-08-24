import type { ChildProcessWithoutNullStreams } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs";

import { getPythonEnvironmentPath } from "../Config/environment";
import { dbInsertRunHistory, dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import type { DictProjectRunDetail } from "../../shared/run";
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

type RunHistoryTerminalStatus = "cancel" | "completed" | "error" | "timeout";

interface RunningPythonProcess {
  processPy: ChildProcessWithoutNullStreams;
  strRunId: string;
}

const mapProcessCache = new Map<number, RunningPythonProcess>();

export async function pythonRun(dictDetail: DictProjectRunDetail): Promise<void> {
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

  const intRunHistoryId = await createRunHistory({
    processPy,
    runId: strRunId,
    runStatePath: strRunStatePath,
    runState: dictRunState,
    detail: dictDetail,
    diagnosticOutput,
  });

  mapProcessCache.set(intRunHistoryId, { processPy, strRunId });

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

    let strRunHistoryStatus: RunHistoryTerminalStatus = "error";
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
  detail: DictProjectRunDetail;
  diagnosticOutput: DictPythonProcessDiagnosticOutput;
}): Promise<number> {
  try {
    const intRunHistoryIdValue = dbInsertRunHistory({
      schedule_name: detail.schedule_name,
      project_source: detail.project_source,
      project_id: detail.id,
      project_name: detail.name,
      project_version: detail.version,
      python_environment_name: detail.python_environment_name,
      run_started_at_ms: parseExecutorRunTimestamp(runState.startedAt),
      status: "running",
      log_path: runState.logPath,
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
