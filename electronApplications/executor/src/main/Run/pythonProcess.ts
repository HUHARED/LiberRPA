// FileName: pythonProcess.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { isProcessRunning } from "../Common/process";
import { buildPythonProcessEnvironment } from "../Config/environment";
import { getConsoleContextEnvironment } from "../Console/consoleContextBridge";
import { loggerMain } from "../Logging/logger";
import { getExecutorRunArgumentsPath, removeExecutorRunArgumentsFile } from "./runState";
import type { ProjectRunConfig } from "./types";

export class PythonProcessNotStartedError extends Error {}

export interface PythonProcessDiagnosticOutput {
  stdoutTail: string;
  stderrTail: string;
}

interface StartedProjectPythonProcess {
  processPy: ChildProcessWithoutNullStreams;
  diagnosticOutput: PythonProcessDiagnosticOutput;
  getProcessError: () => Error | undefined;
}

const STR_PROJECT_RUN_TERMINATION_MESSAGE = "Executor-terminated";
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
): PythonProcessDiagnosticOutput {
  const dictDiagnosticOutput: PythonProcessDiagnosticOutput = {
    stdoutTail: "",
    stderrTail: "",
  };

  processPy.stdout.setEncoding("utf8");
  processPy.stderr.setEncoding("utf8");

  processPy.stdout.on("data", (strChunk: string) => {
    dictDiagnosticOutput.stdoutTail = appendProcessOutputTail(
      dictDiagnosticOutput.stdoutTail,
      strChunk,
    );
  });

  processPy.stderr.on("data", (strChunk: string) => {
    dictDiagnosticOutput.stderrTail = appendProcessOutputTail(
      dictDiagnosticOutput.stderrTail,
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
  detail: ProjectRunConfig;
  packagePath: string;
  pythonEnvironmentPath: string;
  runId: string;
  startedAt: string;
  runStatePath: string;
}): StartedProjectPythonProcess {
  const strArgumentsPath = getExecutorRunArgumentsPath(runId);
  const strArguments = JSON.stringify({
    logLevel: detail.builtin_log_level,
    recordVideo: detail.builtin_record_video,
    stopShortcut: detail.builtin_stop_shortcut,
    highlightUi: detail.builtin_highlight_ui,
    customPrjArgs: detail.custom_prj_args,
  });
  const removeArgumentsFile = (): void => removeExecutorRunArgumentsFile(runId);

  // Open exclusively so a failed launch cannot overwrite another run's arguments.
  let boolArgumentsCreated = false;
  let processPy: ChildProcessWithoutNullStreams;
  try {
    const intArgumentsFd = fs.openSync(strArgumentsPath, "wx");
    boolArgumentsCreated = true;
    try {
      fs.writeFileSync(intArgumentsFd, strArguments, "utf8");
    } finally {
      fs.closeSync(intArgumentsFd);
    }

    processPy = spawn(
      path.join(pythonEnvironmentPath, "python.exe"),
      ["-m", "liberrpa.FlowControl.Run"],
      {
        cwd: packagePath,
        env: buildPythonProcessEnvironment({
          pythonEnvironmentPath,
          pythonPathEntries: [packagePath, path.join(packagePath, "_Components")],
          additionalVariables: {
            // Clear inherited Editor metadata when the Executor bridge is unavailable.
            ...getConsoleContextEnvironment(),
            LIBERRPA_RUN_STARTED_AT: startedAt,
            LIBERRPA_EXECUTOR_RUN_ID: runId,
            LIBERRPA_EXECUTOR_RUN_STATE_PATH: runStatePath,
            LIBERRPA_EXECUTOR_PACKAGE_NAME: detail.project_name,
            LIBERRPA_EXECUTOR_PACKAGE_VERSION: detail.project_version,
          },
        }),
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
  } catch (e: unknown) {
    if (boolArgumentsCreated) removeArgumentsFile();
    // This block has not returned a child process; no automation could have started.
    throw new PythonProcessNotStartedError(getErrorMessage(e), { cause: e });
  }

  // Spawned Python workers re-import the run arguments, so keep the file until close.
  processPy.once("close", removeArgumentsFile);

  const diagnosticOutput = attachPythonDiagnosticStreams(processPy);
  let processError: Error | undefined;

  processPy.on("error", (e: Error) => {
    processError = e;
    loggerMain.error(
      `Python process error for ${detail.project_name}-${detail.project_version} (${runId}): ${e.message}`,
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
  diagnosticOutput: PythonProcessDiagnosticOutput;
}): void {
  const strStdoutTail = diagnosticOutput.stdoutTail.trim();
  const strStderrTail = diagnosticOutput.stderrTail.trim();

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

export function requestPythonTermination(
  processPy: ChildProcessWithoutNullStreams,
  runId: string,
): boolean {
  if (
    !isProcessRunning(processPy) ||
    processPy.stdin.destroyed ||
    !processPy.stdin.writable
  ) {
    return false;
  }

  try {
    processPy.stdin.end(`${STR_PROJECT_RUN_TERMINATION_MESSAGE}\r\n`);
    return true;
  } catch (e: unknown) {
    loggerMain.error(
      `Failed to send shutdown signal to Python process ${runId}: ${getErrorMessage(e)}`,
    );
    return false;
  }
}

function waitForPythonProcessClose(
  processPy: ChildProcessWithoutNullStreams,
): Promise<boolean> {
  if (!isProcessRunning(processPy)) {
    return Promise.resolve(true);
  }

  return new Promise<boolean>((resolve) => {
    const handleClose = (): void => {
      clearTimeout(timeoutId);
      resolve(true);
    };

    const timeoutId = setTimeout(() => {
      processPy.removeListener("close", handleClose);
      resolve(!isProcessRunning(processPy));
    }, INT_PROCESS_TERMINATION_WAIT_MS);

    processPy.once("close", handleClose);
  });
}

export async function waitForPythonProcessTermination(
  processPy: ChildProcessWithoutNullStreams,
  runId: string,
  onForceTerminationRequired?: () => void,
): Promise<void> {
  if (await waitForPythonProcessClose(processPy)) {
    return;
  }

  loggerMain.error(`Python process ${runId} did not terminate within the wait period.`);
  onForceTerminationRequired?.();

  try {
    processPy.kill();
  } catch (e: unknown) {
    loggerMain.error(
      `Failed to force-terminate Python process ${runId}: ${getErrorMessage(e)}`,
    );
    return;
  }

  if (!(await waitForPythonProcessClose(processPy))) {
    loggerMain.error(`Python process ${runId} remained active after force termination.`);
  }
}

export async function terminatePythonProcessAfterStartupFailure(
  processPy: ChildProcessWithoutNullStreams,
  runId: string,
): Promise<void> {
  if (!isProcessRunning(processPy)) {
    return;
  }

  try {
    processPy.kill();
  } catch (e: unknown) {
    loggerMain.error(
      `Failed to terminate Python process ${runId} after startup failure: ${getErrorMessage(e)}`,
    );
    return;
  }

  await waitForPythonProcessTermination(processPy, runId);
}
