// FileName: pythonFunc.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { spawn } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { getPythonEnvironmentPath, strDocumentsFolderPath } from "./commonFunc";
import { dbInsertHistoryDetail, dbUpdateHistoryDetail } from "./database";
import { getExecutorPackageFolderPath } from "./fileFunc";
import { loggerMain } from "./logger";
import { sendMainMessage } from "./ipcMainMessage";
import type { DictColumns_Project_Detail_Run } from "../shared/interface";

type ExecutorRunStateStatus = "running" | "completed" | "error" | "terminated";
type ExecutorHistoryStatus = "cancel" | "completed" | "error" | "timeout";

interface ExecutorRunState {
  schemaVersion: 1;
  runId: string;
  packageName: string;
  packageVersion: string;
  startedAt: string;
  logPath: string;
  status: ExecutorRunStateStatus;
  endedAt?: string;
}

interface DictPythonProcessDiagnosticOutput {
  strStdoutTail: string;
  strStderrTail: string;
}

interface RunningPythonProcess {
  processPy: ChildProcessWithoutNullStreams;
  strRunId: string;
}

const INT_PROCESS_OUTPUT_TAIL_MAX_LENGTH = 32 * 1024;
const INT_INITIAL_RUN_STATE_INTERVAL_MS = 250;
const INT_INITIAL_RUN_STATE_TIMEOUT_MS = 15 * 1000;
const INT_PROCESS_TERMINATION_WAIT_MS = 3 * 1000;
const REGEX_ISO_TIMESTAMP_WITH_TIMEZONE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;

const mapProcessCache = new Map<number, RunningPythonProcess>();
const strExecutorRunStateFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA/ExecutorRunState",
);

export async function pythonRun(
  dictDetail: DictColumns_Project_Detail_Run,
  webContentsObj: Electron.WebContents,
): Promise<void> {
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
  fs.mkdirSync(strExecutorRunStateFolderPath, { recursive: true });
  const strRunStatePath = path.join(strExecutorRunStateFolderPath, `${strRunId}.json`);

  const processPy = spawn(
    path.join(strPythonEnvironmentPath, "python.exe"),
    [
      "-m",
      "liberrpa.FlowControl.Run",
      "--executor_args",
      JSON.stringify({
        logLevel: dictDetail.builtin_log_level,
        recordVideo: dictDetail.builtin_record_video,
        stopShortcut: dictDetail.builtin_stop_shortcut,
        highlightUi: dictDetail.builtin_highlight_ui,
        customPrjArgs: dictDetail.custom_prj_args,
      }),
    ],
    {
      cwd: strExecutorPackagePath,
      env: {
        ...process.env,
        LIBERRPA_RUN_STARTED_AT: strStartedAt,
        LIBERRPA_EXECUTOR_RUN_ID: strRunId,
        LIBERRPA_EXECUTOR_RUN_STATE_PATH: strRunStatePath,
        LIBERRPA_EXECUTOR_PACKAGE_NAME: dictDetail.name,
        LIBERRPA_EXECUTOR_PACKAGE_VERSION: dictDetail.version,
        PATH: [
          strPythonEnvironmentPath,
          path.join(strPythonEnvironmentPath, "Library", "mingw-w64", "bin"),
          path.join(strPythonEnvironmentPath, "Library", "usr", "bin"),
          path.join(strPythonEnvironmentPath, "Library", "bin"),
          path.join(strPythonEnvironmentPath, "Scripts"),
          path.join(strPythonEnvironmentPath, "bin"),
          process.env.PATH ?? "",
        ]
          .filter(Boolean)
          .join(path.delimiter),
        PYTHONPATH: [
          strExecutorPackagePath,
          path.join(strExecutorPackagePath, "_Components"),
          process.env.PYTHONPATH ?? "",
        ]
          .filter(Boolean)
          .join(path.delimiter),
      },
      stdio: ["pipe", "pipe", "pipe"],
    },
  );

  const dictDiagnosticOutput = attachPythonDiagnosticStreams(processPy);
  let processError: Error | undefined;

  processPy.on("error", (e: Error) => {
    processError = e;
    loggerMain.error(
      `Python process error for ${dictDetail.name}-${dictDetail.version} (${strRunId}): ${e.message}`,
    );
  });

  const dictRunState = await getInitialRunState({
    processPy,
    getProcessError: () => processError,
    runId: strRunId,
    runStatePath: strRunStatePath,
    packageName: dictDetail.name,
    packageVersion: dictDetail.version,
    diagnosticOutput: dictDiagnosticOutput,
  });

  loggerMain.debug(`Executor run state is available: ${strRunId}`);

  const intHistoryId = await createTaskHistory({
    processPy,
    runId: strRunId,
    runStatePath: strRunStatePath,
    runState: dictRunState,
    detail: dictDetail,
    diagnosticOutput: dictDiagnosticOutput,
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
    let boolUnexpectedProcessFailure = processError !== undefined;
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
        diagnosticOutput: dictDiagnosticOutput,
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

      sendMainMessage(webContentsObj, { type: "pythonTaskEnded" });
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

function appendProcessOutputTail(strCurrent: string, strChunk: string): string {
  const strCombined = strCurrent + strChunk;

  if (strCombined.length <= INT_PROCESS_OUTPUT_TAIL_MAX_LENGTH) {
    return strCombined;
  }

  return strCombined.slice(-INT_PROCESS_OUTPUT_TAIL_MAX_LENGTH);
}

function attachPythonDiagnosticStreams(
  processPy: ChildProcessWithoutNullStreams,
): DictPythonProcessDiagnosticOutput {
  const dictDiagnosticOutput: DictPythonProcessDiagnosticOutput = {
    strStdoutTail: "",
    strStderrTail: "",
  };

  processPy.stdout.setEncoding("utf8");
  processPy.stderr.setEncoding("utf8");

  processPy.stdout.on("data", (strChunk: string) => {
    dictDiagnosticOutput.strStdoutTail = appendProcessOutputTail(
      dictDiagnosticOutput.strStdoutTail,
      strChunk,
    );
  });

  processPy.stderr.on("data", (strChunk: string) => {
    dictDiagnosticOutput.strStderrTail = appendProcessOutputTail(
      dictDiagnosticOutput.strStderrTail,
      strChunk,
    );
  });

  processPy.stdin.on("error", (e: Error) => {
    loggerMain.debug(`Python stdin closed: ${e.message}`);
  });

  return dictDiagnosticOutput;
}

function logPythonDiagnosticOutput({
  runId,
  reason,
  diagnosticOutput,
}: {
  runId: string;
  reason: string;
  diagnosticOutput: DictPythonProcessDiagnosticOutput;
}): void {
  const strStdoutTail = diagnosticOutput.strStdoutTail.trim();
  const strStderrTail = diagnosticOutput.strStderrTail.trim();

  if (strStdoutTail.length === 0 && strStderrTail.length === 0) {
    return;
  }

  loggerMain.error(`Python process diagnostic output for run ${runId}: ${reason}`);

  if (strStdoutTail.length > 0) {
    loggerMain.error(`Python stdout tail:\r\n${strStdoutTail}`);
  }

  if (strStderrTail.length > 0) {
    loggerMain.error(`Python stderr tail:\r\n${strStderrTail}`);
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}

function isPythonProcessRunning(processPy: ChildProcessWithoutNullStreams): boolean {
  return processPy.exitCode === null && processPy.signalCode === null;
}

function requestPythonTermination(
  processPy: ChildProcessWithoutNullStreams,
  strRunId: string,
): boolean {
  if (
    !isPythonProcessRunning(processPy) ||
    processPy.stdin.destroyed ||
    !processPy.stdin.writable
  ) {
    return false;
  }

  try {
    processPy.stdin.end("Executor-terminated\r\n");
    return true;
  } catch (e: unknown) {
    loggerMain.error(
      `Failed to send shutdown signal to Python process ${strRunId}: ${getErrorMessage(e)}`,
    );
    return false;
  }
}

async function terminatePythonProcessAfterStartupFailure(
  processPy: ChildProcessWithoutNullStreams,
  strRunId: string,
): Promise<void> {
  if (!isPythonProcessRunning(processPy)) {
    return;
  }

  try {
    processPy.kill();
  } catch (e: unknown) {
    loggerMain.error(
      `Failed to terminate Python process ${strRunId} after startup failure: ${getErrorMessage(e)}`,
    );
    return;
  }

  await waitForPythonProcessTermination(processPy, strRunId);
}

async function waitForPythonProcessTermination(
  processPy: ChildProcessWithoutNullStreams,
  strRunId: string,
): Promise<void> {
  if (await waitForPythonProcessClose(processPy)) {
    return;
  }

  loggerMain.error(`Python process ${strRunId} did not terminate within the wait period.`);

  try {
    processPy.kill();
  } catch (e: unknown) {
    loggerMain.error(
      `Failed to force-terminate Python process ${strRunId}: ${getErrorMessage(e)}`,
    );
    return;
  }

  if (!(await waitForPythonProcessClose(processPy))) {
    loggerMain.error(`Python process ${strRunId} remained active after force termination.`);
  }
}

function waitForPythonProcessClose(
  processPy: ChildProcessWithoutNullStreams,
): Promise<boolean> {
  if (!isPythonProcessRunning(processPy)) {
    return Promise.resolve(true);
  }

  return new Promise<boolean>((resolve) => {
    const handleClose = (): void => {
      clearTimeout(timeoutId);
      resolve(true);
    };

    const timeoutId = setTimeout(() => {
      processPy.removeListener("close", handleClose);
      resolve(!isPythonProcessRunning(processPy));
    }, INT_PROCESS_TERMINATION_WAIT_MS);

    processPy.once("close", handleClose);
  });
}

function removeExecutorRunStateFile(strRunStatePath: string): void {
  try {
    fs.rmSync(strRunStatePath, { force: true });
  } catch (e: unknown) {
    loggerMain.warn(
      `Failed to remove Executor run-state file ${strRunStatePath}: ${getErrorMessage(e)}`,
    );
  }
}

function isValidExecutorRunTimestamp(value: string): boolean {
  if (!REGEX_ISO_TIMESTAMP_WITH_TIMEZONE.test(value)) {
    return false;
  }

  const intTimestampMs = Date.parse(value);
  return Number.isSafeInteger(intTimestampMs) && intTimestampMs >= 0;
}

function parseExecutorRunTimestamp(strTimestamp: string): number {
  const intTimestampMs = Date.parse(strTimestamp);
  if (
    !REGEX_ISO_TIMESTAMP_WITH_TIMEZONE.test(strTimestamp) ||
    !Number.isSafeInteger(intTimestampMs) ||
    intTimestampMs < 0
  ) {
    throw new Error(`Invalid Executor run timestamp: ${strTimestamp}`);
  }
  return intTimestampMs;
}

function readExecutorRunState({
  filePath,
  expectedRunId,
  expectedPackageName,
  expectedPackageVersion,
}: {
  filePath: string;
  expectedRunId: string;
  expectedPackageName: string;
  expectedPackageVersion: string;
}): ExecutorRunState {
  const strContent = fs.readFileSync(filePath, { encoding: "utf-8" });
  const value: unknown = JSON.parse(strContent);

  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Executor run state must be a JSON object.");
  }

  const dictState = value as Partial<ExecutorRunState>;
  const setValidStatus = new Set<ExecutorRunStateStatus>([
    "running",
    "completed",
    "error",
    "terminated",
  ]);

  if (
    dictState.schemaVersion !== 1 ||
    dictState.runId !== expectedRunId ||
    dictState.packageName !== expectedPackageName ||
    dictState.packageVersion !== expectedPackageVersion ||
    typeof dictState.startedAt !== "string" ||
    !isValidExecutorRunTimestamp(dictState.startedAt) ||
    typeof dictState.logPath !== "string" ||
    dictState.logPath.length === 0 ||
    typeof dictState.status !== "string" ||
    !setValidStatus.has(dictState.status as ExecutorRunStateStatus) ||
    (dictState.status === "running" && dictState.endedAt !== undefined) ||
    (dictState.status !== "running" &&
      (typeof dictState.endedAt !== "string" ||
        !isValidExecutorRunTimestamp(dictState.endedAt)))
  ) {
    throw new Error(`Invalid Executor run state: ${filePath}`);
  }

  return dictState as ExecutorRunState;
}

async function waitForExecutorRunStateAvailable({
  filePath,
  processPy,
  getProcessError,
  expectedRunId,
  expectedPackageName,
  expectedPackageVersion,
}: {
  filePath: string;
  processPy: ChildProcessWithoutNullStreams;
  getProcessError: () => Error | undefined;
  expectedRunId: string;
  expectedPackageName: string;
  expectedPackageVersion: string;
}): Promise<ExecutorRunState> {
  let intElapsedMs = 0;

  while (intElapsedMs < INT_INITIAL_RUN_STATE_TIMEOUT_MS) {
    const processError = getProcessError();
    if (processError !== undefined) {
      throw new Error(`Python process failed to start: ${processError.message}`, {
        cause: processError,
      });
    }

    if (fs.existsSync(filePath)) {
      return readExecutorRunState({
        filePath,
        expectedRunId,
        expectedPackageName,
        expectedPackageVersion,
      });
    }

    if (!isPythonProcessRunning(processPy)) {
      throw new Error(
        `Python exited before publishing the initial Executor run state: ${expectedRunId}`,
      );
    }

    await new Promise<void>((resolve) => {
      setTimeout(resolve, INT_INITIAL_RUN_STATE_INTERVAL_MS);
    });
    intElapsedMs += INT_INITIAL_RUN_STATE_INTERVAL_MS;
  }

  throw new Error(`Timeout waiting for the initial Executor run state: ${expectedRunId}`);
}

export function pythonCancel(
  historyId: number,
  webContentsObj: Electron.WebContents,
): void {
  const runningProcess = mapProcessCache.get(historyId);
  if (runningProcess !== undefined) {
    if (!requestPythonTermination(runningProcess.processPy, runningProcess.strRunId)) {
      loggerMain.debug(`Python process for Task History ${historyId} is already closing.`);
    }
    return;
  }

  loggerMain.debug(`No running Python process is cached for Task History ${historyId}.`);

  sendMainMessage(webContentsObj, { type: "pythonTaskEnded" });
}
