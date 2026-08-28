// FileName: componentManagementClient.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import {
  buildPythonProcessEnvironment,
  strDefaultPythonEnvironmentPath,
} from "../Config/environment";
import { loggerMain } from "../Logging/logger";
import {
  createValidatePackagedFlowProjectRequest,
  validatePackagedFlowProjectResponse,
} from "./componentManagementProtocol";
import type { Dict_Request_ValidatePackagedFlowProject } from "./componentManagementProtocol";

const INT_COMPONENT_MANAGEMENT_TIMEOUT_MS = 5 * 60 * 1000;
const INT_COMPONENT_MANAGEMENT_STDOUT_MAX_BYTES = 4 * 1024 ** 2;
const INT_COMPONENT_MANAGEMENT_STDERR_MAX_BYTES = 4 * 1024 ** 2;
const INT_COMPONENT_MANAGEMENT_STDERR_TAIL_MAX_LENGTH = 64 * 1024;
const INT_COMPONENT_MANAGEMENT_TERMINATION_WAIT_MS = 3 * 1000;

type Str_ComponentManagementTerminationReason =
  | "requestError"
  | "stderrLimit"
  | "stdoutLimit"
  | "timeout";

function isProcessRunning(processPy: ChildProcessWithoutNullStreams): boolean {
  return processPy.exitCode === null && processPy.signalCode === null;
}

function appendTextTail(
  strCurrent: string,
  strChunk: string,
  intMaxLength: number,
): string {
  const strCombined = strCurrent + strChunk;
  return strCombined.length <= intMaxLength
    ? strCombined
    : strCombined.slice(-intMaxLength);
}

function getStderrDescription(strStderrTail: string, boolStderrTruncated: boolean): string {
  const strOutput = strStderrTail.trimEnd();
  if (strOutput.length === 0) {
    return "";
  }

  const strLabel = boolStderrTruncated
    ? "Component Management stderr tail (earlier output omitted)"
    : "Component Management stderr";
  return `\n${strLabel}:\n${strOutput}`;
}

async function runComponentManagement(
  request: Dict_Request_ValidatePackagedFlowProject,
): Promise<void> {
  const strPythonExecutablePath = path.join(strDefaultPythonEnvironmentPath, "python.exe");
  if (
    !fs.existsSync(strPythonExecutablePath) ||
    !fs.statSync(strPythonExecutablePath).isFile()
  ) {
    throw new Error(
      `The LiberRPA Python executable was not found: ${strPythonExecutablePath}`,
    );
  }

  await new Promise<void>((resolve, reject) => {
    const processPy = spawn(
      strPythonExecutablePath,
      ["-m", "liberrpa.ComponentManagement"],
      {
        cwd: strDefaultPythonEnvironmentPath,
        env: buildPythonProcessEnvironment({
          pythonEnvironmentPath: strDefaultPythonEnvironmentPath,
          additionalVariables: {
            PYTHONUTF8: "1",
            PYTHONIOENCODING: "utf-8",
          },
        }),
        shell: false,
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );

    let strStdout = "";
    let intStdoutBytes = 0;
    let intStderrBytes = 0;
    let strStderrTail = "";
    let boolStderrTruncated = false;
    let requestError: Error | undefined;
    let terminationReason: Str_ComponentManagementTerminationReason | undefined;
    let boolSettled = false;
    let timerTimeout: NodeJS.Timeout | undefined;
    let timerTerminationWait: NodeJS.Timeout | undefined;

    const clearTimers = (): void => {
      if (timerTimeout !== undefined) {
        clearTimeout(timerTimeout);
        timerTimeout = undefined;
      }
      if (timerTerminationWait !== undefined) {
        clearTimeout(timerTerminationWait);
        timerTerminationWait = undefined;
      }
    };

    const rejectOnce = (error: Error): void => {
      if (boolSettled) {
        return;
      }
      boolSettled = true;
      clearTimers();
      reject(error);
    };

    const resolveOnce = (): void => {
      if (boolSettled) {
        return;
      }
      boolSettled = true;
      clearTimers();
      resolve();
    };

    const stopProcess = (): void => {
      if (boolSettled || timerTerminationWait !== undefined) {
        return;
      }

      try {
        if (isProcessRunning(processPy)) {
          processPy.kill();
        }
      } catch (e: unknown) {
        rejectOnce(
          new Error(`Failed to terminate Component Management: ${getErrorMessage(e)}`, {
            cause: e,
          }),
        );
        return;
      }

      timerTerminationWait = setTimeout(() => {
        rejectOnce(
          new Error(
            "Component Management remained active after a termination request." +
              getStderrDescription(strStderrTail, boolStderrTruncated),
          ),
        );
      }, INT_COMPONENT_MANAGEMENT_TERMINATION_WAIT_MS);
    };

    const requestTermination = (reason: Str_ComponentManagementTerminationReason): void => {
      if (boolSettled || terminationReason !== undefined) {
        return;
      }
      terminationReason = reason;
      stopProcess();
    };

    processPy.stdout.setEncoding("utf-8");
    processPy.stderr.setEncoding("utf-8");
    processPy.stdout.on("data", (strChunk: string) => {
      if (terminationReason !== undefined) {
        return;
      }

      intStdoutBytes += Buffer.byteLength(strChunk, "utf-8");
      if (intStdoutBytes > INT_COMPONENT_MANAGEMENT_STDOUT_MAX_BYTES) {
        requestTermination("stdoutLimit");
        return;
      }
      strStdout += strChunk;
    });
    processPy.stderr.on("data", (strChunk: string) => {
      intStderrBytes += Buffer.byteLength(strChunk, "utf-8");
      const intCombinedLength = strStderrTail.length + strChunk.length;
      if (intCombinedLength > INT_COMPONENT_MANAGEMENT_STDERR_TAIL_MAX_LENGTH) {
        boolStderrTruncated = true;
      }
      strStderrTail = appendTextTail(
        strStderrTail,
        strChunk,
        INT_COMPONENT_MANAGEMENT_STDERR_TAIL_MAX_LENGTH,
      );
      if (
        intStderrBytes > INT_COMPONENT_MANAGEMENT_STDERR_MAX_BYTES &&
        terminationReason === undefined
      ) {
        requestTermination("stderrLimit");
      }
    });
    processPy.once("error", (e: Error) => {
      if (terminationReason === undefined) {
        rejectOnce(
          new Error(`Component Management process error: ${e.message}`, { cause: e }),
        );
      }
    });
    processPy.stdin.once("error", (e: Error) => {
      requestError = e;
      if (isProcessRunning(processPy)) {
        requestTermination("requestError");
      }
    });

    processPy.once(
      "close",
      (intExitCode: number | null, strSignal: NodeJS.Signals | null) => {
        if (boolSettled) {
          return;
        }

        const strStderrDescription = getStderrDescription(
          strStderrTail,
          boolStderrTruncated,
        );
        if (strStderrDescription.length > 0) {
          loggerMain.debug(strStderrDescription.slice(1));
        }

        if (terminationReason === "requestError") {
          const error = requestError ?? new Error("Unknown request error.");
          rejectOnce(
            new Error(
              `Failed to send the Component Management request: ${error.message}` +
                strStderrDescription,
              { cause: error },
            ),
          );
          return;
        }
        if (terminationReason === "timeout") {
          rejectOnce(
            new Error(
              `Component Management timed out after ${String(
                INT_COMPONENT_MANAGEMENT_TIMEOUT_MS / 1000,
              )} seconds.` + strStderrDescription,
            ),
          );
          return;
        }
        if (terminationReason === "stderrLimit") {
          rejectOnce(
            new Error(
              `Component Management stderr exceeded the ${String(
                INT_COMPONENT_MANAGEMENT_STDERR_MAX_BYTES / 1024 ** 2,
              )} MiB output limit.` + strStderrDescription,
            ),
          );
          return;
        }
        if (terminationReason === "stdoutLimit") {
          rejectOnce(
            new Error(
              `Component Management stdout exceeded the ${String(
                INT_COMPONENT_MANAGEMENT_STDOUT_MAX_BYTES / 1024 ** 2,
              )} MiB protocol limit.` + strStderrDescription,
            ),
          );
          return;
        }
        if (intExitCode !== 0) {
          const strExitInfo =
            strSignal === null ? `exit code ${String(intExitCode)}` : `signal ${strSignal}`;
          rejectOnce(
            new Error(
              `Component Management exited unexpectedly with ${strExitInfo}.` +
                strStderrDescription,
            ),
          );
          return;
        }

        try {
          validatePackagedFlowProjectResponse(strStdout.trim());
          resolveOnce();
        } catch (e: unknown) {
          rejectOnce(new Error(getErrorMessage(e), { cause: e }));
        }
      },
    );

    timerTimeout = setTimeout(() => {
      requestTermination("timeout");
    }, INT_COMPONENT_MANAGEMENT_TIMEOUT_MS);

    try {
      processPy.stdin.end(`${JSON.stringify(request)}\n`);
    } catch (e: unknown) {
      requestError = e instanceof Error ? e : new Error(getErrorMessage(e));
      requestTermination("requestError");
    }
  });
}

export async function validatePackagedFlowProject(projectPath: string): Promise<void> {
  await runComponentManagement(createValidatePackagedFlowProjectRequest(projectPath));
}
