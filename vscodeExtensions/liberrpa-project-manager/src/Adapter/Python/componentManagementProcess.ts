// FileName: componentManagementProcess.ts

import * as fs from "node:fs";
import * as path from "node:path";
import { spawn } from "node:child_process";

import { log } from "../VsCode/output";
import { isRecord, hasExactKeys } from "../../Common/typeCheck";
import type {
  DictComponentManagementWarning_Operation,
  DictComponentManagementWarning_SnippetDiagnostic,
  DictComponentManagementWarning_SnippetConfig,
  DictComponentManagementWarning,
} from "../../Domain/ComponentManagement/componentManagementTypes";
import type {
  DictProtocolRequest,
  DictProtocolResponse_Raw,
} from "./componentManagementProtocol";

const SET_KEYS_WARNING_OPERATION = new Set(["code", "message"]);
const SET_KEYS_WARNING_OPERATION_DETAILS = new Set(["code", "message", "details"]);
const SET_KEYS_WARNING_SNIPPET_DIAGNOSTIC = new Set(["code", "message", "file", "line"]);
const SET_KEYS_WARNING_SNIPPET_DIAGNOSTIC_FUNCTION = new Set([
  "code",
  "message",
  "file",
  "line",
  "functionName",
]);
const SET_KEYS_WARNING_SNIPPET_CONFIG = new Set(["code", "message", "snippetKey"]);
const SET_KEYS_PROTOCOL_SUCCESS = new Set(["schemaVersion", "ok", "result", "warnings"]);
const SET_KEYS_PROTOCOL_ERROR = new Set(["schemaVersion", "ok", "error"]);
const SET_KEYS_PROTOCOL_ERROR_INFO = new Set(["code", "message", "details"]);

function parseComponentManagementWarning(value: unknown): DictComponentManagementWarning {
  if (!isRecord(value)) {
    throw new Error("Component Management returned an invalid warning item.");
  }

  if (hasExactKeys(value, SET_KEYS_WARNING_OPERATION)) {
    const { code, message } = value;
    if (typeof code === "string" && typeof message === "string") {
      return { code, message } satisfies DictComponentManagementWarning_Operation;
    }
  }

  if (hasExactKeys(value, SET_KEYS_WARNING_OPERATION_DETAILS)) {
    const { code, message, details } = value;
    if (typeof code === "string" && typeof message === "string" && isRecord(details)) {
      return {
        code,
        message,
        details,
      } satisfies DictComponentManagementWarning_Operation;
    }
  }

  if (
    hasExactKeys(value, SET_KEYS_WARNING_SNIPPET_DIAGNOSTIC) ||
    hasExactKeys(value, SET_KEYS_WARNING_SNIPPET_DIAGNOSTIC_FUNCTION)
  ) {
    const { code, message, file, line, functionName } = value;
    if (
      typeof code === "string" &&
      typeof message === "string" &&
      typeof file === "string" &&
      Number.isInteger(line) &&
      (functionName === undefined || typeof functionName === "string")
    ) {
      return {
        code,
        message,
        file,
        line: line as number,
        ...(functionName === undefined ? {} : { functionName }),
      } satisfies DictComponentManagementWarning_SnippetDiagnostic;
    }
  }

  if (hasExactKeys(value, SET_KEYS_WARNING_SNIPPET_CONFIG)) {
    const { code, message, snippetKey } = value;
    if (
      typeof code === "string" &&
      typeof message === "string" &&
      typeof snippetKey === "string"
    ) {
      return {
        code,
        message,
        snippetKey,
      } satisfies DictComponentManagementWarning_SnippetConfig;
    }
  }

  throw new Error("Component Management returned an invalid warning item.");
}

function parseComponentManagementResponse(output: string): DictProtocolResponse_Raw {
  let value: unknown;

  try {
    value = JSON.parse(output) as unknown;
  } catch (e: unknown) {
    throw new Error("Component Management returned invalid JSON on stdout.", {
      cause: e,
    });
  }

  if (
    !isRecord(value) ||
    value["schemaVersion"] !== 1 ||
    typeof value["ok"] !== "boolean"
  ) {
    throw new Error("Component Management returned an invalid protocol response.");
  }

  if (value["ok"]) {
    if (
      !hasExactKeys(value, SET_KEYS_PROTOCOL_SUCCESS) ||
      !isRecord(value["result"]) ||
      !Array.isArray(value["warnings"])
    ) {
      throw new Error("Component Management returned an invalid success response.");
    }

    return {
      schemaVersion: 1,
      ok: true,
      result: value["result"],
      warnings: value["warnings"].map(parseComponentManagementWarning),
    };
  }

  if (
    !hasExactKeys(value, SET_KEYS_PROTOCOL_ERROR) ||
    !isRecord(value["error"]) ||
    !hasExactKeys(value["error"], SET_KEYS_PROTOCOL_ERROR_INFO)
  ) {
    throw new Error("Component Management returned an invalid error response.");
  }

  const { code, message, details } = value["error"];
  if (typeof code !== "string" || typeof message !== "string" || !isRecord(details)) {
    throw new Error("Component Management returned invalid error information.");
  }

  return {
    schemaVersion: 1,
    ok: false,
    error: { code, message, details },
  };
}

function getPythonEnvironmentInfo(): {
  pythonExecutablePath: string;
  pythonEnvironmentPath: string;
  environment: NodeJS.ProcessEnv;
} {
  const strLiberRPAPath = process.env.LiberRPA;
  if (strLiberRPAPath === undefined || strLiberRPAPath.trim().length === 0) {
    throw new Error("The LiberRPA User Environment Variable was not found.");
  }

  const strPythonEnvironmentPath = path.join(strLiberRPAPath, "envs", "pyenv");
  const strPythonExecutablePath = path.join(strPythonEnvironmentPath, "python.exe");

  if (
    !fs.existsSync(strPythonExecutablePath) ||
    !fs.statSync(strPythonExecutablePath).isFile()
  ) {
    throw new Error(
      `The LiberRPA Python executable was not found: ${strPythonExecutablePath}`,
    );
  }

  const environment: NodeJS.ProcessEnv = {
    ...process.env,
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    PATH: [
      strPythonEnvironmentPath,
      path.join(strPythonEnvironmentPath, "Library", "mingw-w64", "bin"),
      path.join(strPythonEnvironmentPath, "Library", "usr", "bin"),
      path.join(strPythonEnvironmentPath, "Library", "bin"),
      path.join(strPythonEnvironmentPath, "Scripts"),
      path.join(strPythonEnvironmentPath, "bin"),
      process.env.PATH ?? "",
    ]
      .filter((item) => item.length > 0)
      .join(path.delimiter),
  };

  return {
    pythonExecutablePath: strPythonExecutablePath,
    pythonEnvironmentPath: strPythonEnvironmentPath,
    environment,
  };
}

export async function runComponentManagement(
  requestInfo: DictProtocolRequest,
): Promise<DictProtocolResponse_Raw> {
  const { pythonExecutablePath, pythonEnvironmentPath, environment } =
    getPythonEnvironmentInfo();

  return await new Promise<DictProtocolResponse_Raw>((resolve, reject) => {
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
    let requestWriteError: Error | undefined;

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
        const strStderrOutput = strStderr.trimEnd();

        if (processError !== undefined) {
          if (strStderrOutput.length > 0) {
            log.error(`Component Management stderr:\n${strStderrOutput}`);
          }
          reject(
            new Error(`Failed to start Component Management: ${processError.message}`, {
              cause: processError,
            }),
          );
          return;
        }

        if (exitCode !== 0) {
          if (strStderrOutput.length > 0) {
            log.error(`Component Management stderr:\n${strStderrOutput}`);
          }
          const strExitInfo =
            signal === null ? `exit code ${String(exitCode)}` : `signal ${signal}`;
          reject(
            new Error(
              `Component Management exited unexpectedly with ${strExitInfo}.` +
                (strStderrOutput.length > 0 ? `\n${strStderrOutput.trim()}` : ""),
            ),
          );
          return;
        }

        if (requestWriteError !== undefined) {
          if (strStderrOutput.length > 0) {
            log.error(`Component Management stderr:\n${strStderrOutput}`);
          }
          reject(
            new Error(
              `Failed to send the request to Component Management: ${requestWriteError.message}`,
              { cause: requestWriteError },
            ),
          );
          return;
        }

        const strProtocolOutput = strStdout.trim();
        if (strProtocolOutput.length === 0) {
          if (strStderrOutput.length > 0) {
            log.error(`Component Management stderr:\n${strStderrOutput}`);
          }
          reject(new Error("Component Management returned no protocol response."));
          return;
        }

        let response: DictProtocolResponse_Raw;
        try {
          response = parseComponentManagementResponse(strProtocolOutput);
        } catch (e: unknown) {
          if (strStderrOutput.length > 0) {
            log.error(`Component Management stderr:\n${strStderrOutput}`);
          }
          reject(e instanceof Error ? e : new Error(String(e)));
          return;
        }

        if (strStderrOutput.length > 0) {
          const strMessage = `Component Management stderr:\n${strStderrOutput}`;
          if (response.ok) {
            log.warn(strMessage);
          } else {
            log.error(strMessage);
          }
        }

        resolve(response);
      },
    );

    pythonProcess.stdin.once("error", (error: Error) => {
      requestWriteError = error;
    });

    try {
      pythonProcess.stdin.end(JSON.stringify(requestInfo));
    } catch (e: unknown) {
      requestWriteError = e instanceof Error ? e : new Error(String(e));
      pythonProcess.kill();
    }
  });
}
