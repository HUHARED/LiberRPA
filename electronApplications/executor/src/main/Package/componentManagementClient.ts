import { spawn } from "child_process";
import path from "path";
import fs from "fs";

import {
  getPythonProcessEnvironment,
  strDefaultPythonEnvironmentPath,
} from "../Config/environment";
import { loggerMain } from "../Logging/logger";
import { isRecord } from "../Common/validation";

const SET_SUCCESS_KEYS = new Set(["schemaVersion", "ok", "result", "warnings"]);
const SET_SUCCESS_RESULT_KEYS = new Set(["status"]);
const SET_FAILURE_KEYS = new Set(["schemaVersion", "ok", "error"]);
const SET_ERROR_KEYS = new Set(["code", "message", "details"]);

function hasExactKeys(value: Record<string, unknown>, expectedKeys: Set<string>): boolean {
  const arrKey = Object.keys(value);
  return (
    arrKey.length === expectedKeys.size &&
    arrKey.every((strKey) => expectedKeys.has(strKey))
  );
}

function validateComponentManagementResponse(strOutput: string): void {
  let value: unknown;
  try {
    value = JSON.parse(strOutput);
  } catch (e: unknown) {
    throw new Error("Component Management returned invalid JSON on stdout.", {
      cause: e,
    });
  }

  if (!isRecord(value) || value.schemaVersion !== 1 || typeof value.ok !== "boolean") {
    throw new Error("Component Management returned an invalid protocol response.");
  }

  if (value.ok) {
    if (
      !hasExactKeys(value, SET_SUCCESS_KEYS) ||
      !isRecord(value.result) ||
      !hasExactKeys(value.result, SET_SUCCESS_RESULT_KEYS) ||
      value.result.status !== "packagedFlowProjectValidated" ||
      !Array.isArray(value.warnings)
    ) {
      throw new Error("Component Management returned an invalid success response.");
    }
    return;
  }

  if (
    !hasExactKeys(value, SET_FAILURE_KEYS) ||
    !isRecord(value.error) ||
    !hasExactKeys(value.error, SET_ERROR_KEYS) ||
    typeof value.error.code !== "string" ||
    typeof value.error.message !== "string" ||
    !isRecord(value.error.details)
  ) {
    throw new Error("Component Management returned an invalid error response.");
  }

  const strDetails = JSON.stringify(value.error.details, null, 2);
  throw new Error(
    `[${value.error.code}] ${value.error.message}` +
      (strDetails === "{}" ? "" : `\n${strDetails}`),
  );
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function runComponentManagement(request: Record<string, unknown>): Promise<void> {
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
        env: getPythonProcessEnvironment({
          pythonEnvironmentPath: strDefaultPythonEnvironmentPath,
          variables: {
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
    let strStderr = "";
    let processError: Error | undefined;
    let requestError: Error | undefined;

    processPy.stdout.setEncoding("utf-8");
    processPy.stderr.setEncoding("utf-8");
    processPy.stdout.on("data", (strChunk: string) => {
      strStdout += strChunk;
    });
    processPy.stderr.on("data", (strChunk: string) => {
      strStderr += strChunk;
    });
    processPy.once("error", (e: Error) => {
      processError = e;
    });
    processPy.stdin.once("error", (e: Error) => {
      requestError = e;
    });

    processPy.once(
      "close",
      (intExitCode: number | null, strSignal: NodeJS.Signals | null) => {
        const strStderrOutput = strStderr.trimEnd();
        if (strStderrOutput.length > 0) {
          loggerMain.debug(`Component Management stderr:\n${strStderrOutput}`);
        }

        if (processError !== undefined) {
          reject(
            new Error(`Failed to start Component Management: ${processError.message}`, {
              cause: processError,
            }),
          );
          return;
        }
        if (requestError !== undefined) {
          reject(
            new Error(
              `Failed to send the Component Management request: ${requestError.message}`,
              { cause: requestError },
            ),
          );
          return;
        }
        if (intExitCode !== 0) {
          const strExitInfo =
            strSignal === null ? `exit code ${String(intExitCode)}` : `signal ${strSignal}`;
          reject(
            new Error(
              `Component Management exited unexpectedly with ${strExitInfo}.` +
                (strStderrOutput.length === 0 ? "" : `\n${strStderrOutput}`),
            ),
          );
          return;
        }

        try {
          validateComponentManagementResponse(strStdout.trim());
          resolve();
        } catch (e: unknown) {
          reject(new Error(getErrorMessage(e), { cause: e }));
        }
      },
    );

    processPy.stdin.end(`${JSON.stringify(request)}\n`);
  });
}

export async function validatePackagedFlowProject(strProjectPath: string): Promise<void> {
  await runComponentManagement({
    schemaVersion: 1,
    operation: "validatePackagedFlowProject",
    projectPath: strProjectPath,
  });
}
