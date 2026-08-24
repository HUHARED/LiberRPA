import type { ChildProcessWithoutNullStreams } from "child_process";
import { spawn } from "child_process";
import path from "path";

import { getPythonProcessEnvironment } from "../Config/environment";
import { loggerMain } from "../Logging/logger";
import type { DictProjectRunDetail } from "../../shared/run";

export interface DictPythonProcessDiagnosticOutput {
  strStdoutTail: string;
  strStderrTail: string;
}

interface StartedProjectPythonProcess {
  processPy: ChildProcessWithoutNullStreams;
  diagnosticOutput: DictPythonProcessDiagnosticOutput;
  getProcessError: () => Error | undefined;
}

const INT_PROCESS_OUTPUT_TAIL_MAX_LENGTH = 32 * 1024;
const INT_PROCESS_TERMINATION_WAIT_MS = 3 * 1000;

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

export function spawnProjectPythonProcess({
  detail,
  packagePath,
  pythonEnvironmentPath,
  runId,
  startedAt,
  runStatePath,
}: {
  detail: DictProjectRunDetail;
  packagePath: string;
  pythonEnvironmentPath: string;
  runId: string;
  startedAt: string;
  runStatePath: string;
}): StartedProjectPythonProcess {
  const processPy = spawn(
    path.join(pythonEnvironmentPath, "python.exe"),
    [
      "-m",
      "liberrpa.FlowControl.Run",
      "--executor_args",
      JSON.stringify({
        logLevel: detail.builtin_log_level,
        recordVideo: detail.builtin_record_video,
        stopShortcut: detail.builtin_stop_shortcut,
        highlightUi: detail.builtin_highlight_ui,
        customPrjArgs: detail.custom_prj_args,
      }),
    ],
    {
      cwd: packagePath,
      env: getPythonProcessEnvironment({
        pythonEnvironmentPath,
        pythonPathEntries: [packagePath, path.join(packagePath, "_Components")],
        variables: {
          LIBERRPA_RUN_STARTED_AT: startedAt,
          LIBERRPA_EXECUTOR_RUN_ID: runId,
          LIBERRPA_EXECUTOR_RUN_STATE_PATH: runStatePath,
          LIBERRPA_EXECUTOR_PACKAGE_NAME: detail.name,
          LIBERRPA_EXECUTOR_PACKAGE_VERSION: detail.version,
        },
      }),
      stdio: ["pipe", "pipe", "pipe"],
    },
  );

  const diagnosticOutput = attachPythonDiagnosticStreams(processPy);
  let processError: Error | undefined;

  processPy.on("error", (e: Error) => {
    processError = e;
    loggerMain.error(
      `Python process error for ${detail.name}-${detail.version} (${runId}): ${e.message}`,
    );
  });

  return {
    processPy,
    diagnosticOutput,
    getProcessError: () => processError,
  };
}

export function logPythonDiagnosticOutput({
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

export function isPythonProcessRunning(processPy: ChildProcessWithoutNullStreams): boolean {
  return processPy.exitCode === null && processPy.signalCode === null;
}

export function requestPythonTermination(
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

export async function terminatePythonProcessAfterStartupFailure(
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

export async function waitForPythonProcessTermination(
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

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}
