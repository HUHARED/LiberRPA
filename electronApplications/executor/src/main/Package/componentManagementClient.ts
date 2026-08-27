// FileName: componentManagementClient.ts

import { spawn } from "child_process";
import fs from "fs";
import path from "path";

import {
  getPythonProcessEnvironment,
  strDefaultPythonEnvironmentPath,
} from "../Config/environment";
import { loggerMain } from "../Logging/logger";
import {
  createValidatePackagedFlowProjectRequest,
  validatePackagedFlowProjectResponse,
} from "./componentManagementProtocol";
import type { Dict_Request_ValidatePackagedFlowProject } from "./componentManagementProtocol";

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
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
          validatePackagedFlowProjectResponse(strStdout.trim());
          resolve();
        } catch (e: unknown) {
          reject(new Error(getErrorMessage(e), { cause: e }));
        }
      },
    );

    processPy.stdin.end(`${JSON.stringify(request)}\n`);
  });
}

export async function validatePackagedFlowProject(projectPath: string): Promise<void> {
  await runComponentManagement(createValidatePackagedFlowProjectRequest(projectPath));
}
