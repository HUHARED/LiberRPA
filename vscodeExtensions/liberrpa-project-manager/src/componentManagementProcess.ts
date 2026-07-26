// FileName: componentManagementProcess.ts
import * as fs from "node:fs";
import * as path from "node:path";
import { spawn } from "node:child_process";

import { log } from "./output";
import { isRecord } from "./typeCheck";

export interface DictComponentManagementWarning {
  code?: string;
  message?: string;
  [key: string]: unknown;
}

interface DictSuccessResponse {
  schemaVersion: 1;
  ok: true;
  result: Record<string, unknown>;
  warnings: DictComponentManagementWarning[];
}

interface DictProtocolError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

interface DictErrorResponse {
  schemaVersion: 1;
  ok: false;
  error: DictProtocolError;
}

type DictProtocolResponse = DictSuccessResponse | DictErrorResponse;

interface DictPublishComponentRequest {
  schemaVersion: 1;
  operation: "publishComponent";
  projectPath: string;
}

function parseComponentManagementResponse(output: string): DictProtocolResponse {
  let value: unknown;

  try {
    value = JSON.parse(output) as unknown;
  } catch (e: unknown) {
    throw new Error("Component Management returned invalid JSON on stdout.", {
      cause: e,
    });
  }

  if (!isRecord(value) || value.schemaVersion !== 1 || typeof value.ok !== "boolean") {
    throw new Error("Component Management returned an invalid protocol response.");
  }

  if (value.ok) {
    if (!isRecord(value.result) || !Array.isArray(value.warnings)) {
      throw new Error("Component Management returned an invalid success response.");
    }

    const arrWarnings: DictComponentManagementWarning[] = [];
    for (const warning of value.warnings) {
      if (!isRecord(warning)) {
        throw new Error("Component Management returned an invalid warning item.");
      }

      arrWarnings.push(warning);
    }

    return {
      schemaVersion: 1,
      ok: true,
      result: value.result,
      warnings: arrWarnings,
    };
  }

  if (!isRecord(value.error)) {
    throw new Error("Component Management returned an invalid error response.");
  }

  const { code, message, details } = value.error;
  if (typeof code !== "string" || typeof message !== "string" || !isRecord(details)) {
    throw new Error("Component Management returned invalid error information.");
  }

  return {
    schemaVersion: 1,
    ok: false,
    error: {
      code,
      message,
      details,
    },
  };
}

function getPythonEnvironmentInfo(): {
  pythonExecutablePath: string;
  pythonEnvironmentPath: string;
  environment: NodeJS.ProcessEnv;
} {
  const strLiberRPAEnvPath = process.env.LiberRPA;
  if (strLiberRPAEnvPath === undefined || strLiberRPAEnvPath.trim().length === 0) {
    throw new Error("The LiberRPA User Environment Variable was not found.");
  }

  const strPyEnvPath = path.join(strLiberRPAEnvPath, "envs/pyenv");
  const strPyExePath = path.join(strPyEnvPath, "python.exe");

  if (!fs.existsSync(strPyExePath) || !fs.statSync(strPyExePath).isFile()) {
    throw new Error(`The LiberRPA Python executable was not found: ${strPyExePath}`);
  }

  const environment: NodeJS.ProcessEnv = {
    ...process.env,
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    PATH: [
      strPyEnvPath,
      path.join(strPyEnvPath, "Library", "mingw-w64", "bin"),
      path.join(strPyEnvPath, "Library", "usr", "bin"),
      path.join(strPyEnvPath, "Library", "bin"),
      path.join(strPyEnvPath, "Scripts"),
      path.join(strPyEnvPath, "bin"),
      process.env.PATH ?? "",
    ]
      .filter((item) => item.length > 0)
      .join(path.delimiter),
  };

  return {
    pythonExecutablePath: strPyExePath,
    pythonEnvironmentPath: strPyEnvPath,
    environment,
  };
}

export async function runComponentManagement(
  requestInfo: DictPublishComponentRequest,
): Promise<DictProtocolResponse> {
  const { pythonExecutablePath, pythonEnvironmentPath, environment } =
    getPythonEnvironmentInfo();

  return await new Promise<DictProtocolResponse>((resolve, reject) => {
    const pythonProcess = spawn(
      pythonExecutablePath,
      ["-m", "liberrpa.ComponentManagement"],
      {
        cwd: pythonEnvironmentPath,
        env: environment,
        shell: false,
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );

    let strStdout = "";
    let strStderr = "";
    let processError: Error | undefined;

    pythonProcess.stdout.setEncoding("utf-8");
    pythonProcess.stderr.setEncoding("utf-8");

    pythonProcess.stdout.on("data", (chunk: string) => {
      strStdout += chunk;
    });

    pythonProcess.stderr.on("data", (chunk: string) => {
      strStderr += chunk;
    });

    pythonProcess.once("error", (error: Error) => {
      processError = error;
    });

    pythonProcess.once(
      "close",
      (exitCode: number | null, signal: NodeJS.Signals | null) => {
        if (strStderr.trim().length > 0) {
          log.debug(`Component Management stderr:\n${strStderr.trimEnd()}`);
        }

        if (processError !== undefined) {
          reject(
            new Error(`Failed to start Component Management: ${processError.message}`, {
              cause: processError,
            }),
          );
          return;
        }

        if (exitCode !== 0) {
          const strExitInfo =
            signal === null ? `exit code ${String(exitCode)}` : `signal ${signal}`;
          reject(
            new Error(
              `Component Management exited unexpectedly with ${strExitInfo}.` +
                (strStderr.trim().length > 0 ? `\n${strStderr.trim()}` : ""),
            ),
          );
          return;
        }

        const protocolOutput = strStdout.trim();
        if (protocolOutput.length === 0) {
          reject(new Error("Component Management returned no protocol response."));
          return;
        }

        try {
          resolve(parseComponentManagementResponse(protocolOutput));
        } catch (e: unknown) {
          reject(e instanceof Error ? e : new Error(String(e)));
        }
      },
    );

    pythonProcess.stdin.once("error", (error: Error) => {
      pythonProcess.kill();

      reject(
        new Error("Failed to send the request to Component Management.", {
          cause: error,
        }),
      );
    });

    try {
      pythonProcess.stdin.end(JSON.stringify(requestInfo));
    } catch (e: unknown) {
      pythonProcess.kill();
      reject(
        new Error("Failed to send the request to Component Management.", {
          cause: e,
        }),
      );
    }
  });
}
