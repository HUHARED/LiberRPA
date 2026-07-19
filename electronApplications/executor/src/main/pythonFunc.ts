// FileName: pythonFunc.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import { spawn } from "child_process";
import { randomUUID } from "crypto";
import path from "path";
import fs from "fs";
import moment from "moment";

import { loggerMain } from "./logger";
import { strExecutorPackageFolderPath } from "./fileFunc";
import { dbInsertHistoryDetail, dbUpdateHistoryDetail } from "./database";
import { strDocumentsFolderPath, strPyEnvPath } from "./commonFunc";
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

const dictProcessCache: { [key: string]: ChildProcessWithoutNullStreams } = {};
const strRunFilePath = path.join(
  strPyEnvPath,
  "Lib/site-packages/liberrpa/FlowControl/Run.py"
);
const strExecutorRunStateFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA/ExecutorRunState"
);

export async function pythonRun(
  dictDetail: DictColumns_Project_Detail_Run,
  webContentsObj: Electron.WebContents
): Promise<void> {
  // NOTE: Only "local" source now.
  const strExecutorPackagePath = path.join(
    strExecutorPackageFolderPath,
    `${dictDetail.name}_${dictDetail.version}`
  );

  if (!fs.existsSync(strExecutorPackagePath)) {
    throw new Error(
      `${dictDetail.name}-${dictDetail.version} does not exist in ${strExecutorPackageFolderPath}.`
    );
  }

  /* Run python. */
  const strRunId = randomUUID();
  const strStartedAt = new Date().toISOString();
  fs.mkdirSync(strExecutorRunStateFolderPath, { recursive: true });
  const strRunStatePath = path.join(strExecutorRunStateFolderPath, `${strRunId}.json`);

  const processPy = spawn(
    path.join(strPyEnvPath, "python.exe"),
    [
      strRunFilePath,
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
      // Follow the values in os.environ.get("PATH") and os.environ.get("PYTHONPATH") when run it in vscode.
      env: {
        ...process.env,
        LIBERRPA_RUN_STARTED_AT: strStartedAt,
        LIBERRPA_EXECUTOR_RUN_ID: strRunId,
        LIBERRPA_EXECUTOR_RUN_STATE_PATH: strRunStatePath,
        LIBERRPA_EXECUTOR_PACKAGE_NAME: dictDetail.name,
        LIBERRPA_EXECUTOR_PACKAGE_VERSION: dictDetail.version,
        PATH: [
          strPyEnvPath,
          path.join(strPyEnvPath, "Library", "mingw-w64", "bin"),
          path.join(strPyEnvPath, "Library", "usr", "bin"),
          path.join(strPyEnvPath, "Library", "bin"),
          path.join(strPyEnvPath, "Scripts"),
          path.join(strPyEnvPath, "bin"),
          process.env.PATH ?? "",
        ]
          .filter(Boolean)
          .join(path.delimiter),
        PYTHONPATH: [strExecutorPackagePath, process.env.PYTHONPATH ?? ""]
          .filter(Boolean)
          .join(path.delimiter),
      },
      stdio: ["pipe", "pipe", "pipe"],
    }
  );

  const dictRunState = await waitForExecutorRunStateAvailable({
    filePath: strRunStatePath,
    processPy,
    expectedRunId: strRunId,
    expectedPackageName: dictDetail.name,
    expectedPackageVersion: dictDetail.version,
  });
  loggerMain.debug(`Executor run state is available: ${strRunId}`);

  // Insert data into database. Only "local" source now.
  const intHistoryId = dbInsertHistoryDetail({
    scheduler_name: dictDetail.scheduler_name,
    project_source: dictDetail.project_source,
    project_id: dictDetail.id,
    project_name: dictDetail.name,
    project_version: dictDetail.version,
    run_start: moment(dictRunState.startedAt).format("YYYY-MM-DD HH:mm:ss"),
    status: "running",
    log_path: dictRunState.logPath,
  }).lastInsertRowid as number;

  dictProcessCache[String(intHistoryId)] = processPy;

  // Set timeout.
  let boolTimeout = false;
  let timeoutId: NodeJS.Timeout | undefined;
  if (dictDetail.timeout_min !== 0) {
    loggerMain.info(`Set timeout: ${dictDetail.timeout_min}`);
    timeoutId = setTimeout(
      () => {
        // Is the Python program is running.
        if (processPy.exitCode === null && processPy.signalCode === null) {
          loggerMain.info(
            `Timeout reached. Stopping ${dictDetail.name}-${dictDetail.version}`
          );
          try {
            processPy.stdin.write("Executor-terminated\n");
            processPy.stdin.end();
            boolTimeout = true;
          } catch (e) {
            loggerMain.error(`Failed to send shutdown signal to Python process: ${e}`);
          }
        }
      },
      dictDetail.timeout_min * 60 * 1000
    );
  }

  /* When the Python process closed. */
  let boolFinalized = false;
  const finalize = (code: number | null): void => {
    if (boolFinalized) {
      return;
    }
    boolFinalized = true;

    loggerMain.info(`${dictDetail.name}-${dictDetail.version} exited with code ${code}`);

    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    let strHistoryStatus: ExecutorHistoryStatus = "error";

    try {
      const dictFinalState = readExecutorRunState({
        filePath: strRunStatePath,
        expectedRunId: strRunId,
        expectedPackageName: dictDetail.name,
        expectedPackageVersion: dictDetail.version,
      });

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
            `Python exited before publishing a final Executor run state: ${strRunId}`
          );
          strHistoryStatus = "error";
          break;
      }
    } catch (e) {
      loggerMain.error(`Failed to read final Executor run state: ${e}`);
    }

    // Update database
    dbUpdateHistoryDetail({
      id: intHistoryId,
      run_end: moment(new Date()).format("YYYY-MM-DD HH:mm:ss"),
      status: strHistoryStatus,
    });

    // Remove cache.
    delete dictProcessCache[String(intHistoryId)];

    webContentsObj.send("send-from-main", "pythonResult:taskEnd");
  };

  processPy.once("close", finalize);

  // The process may have exited after the initial state was read but before the listener was registered.
  if (processPy.exitCode !== null || processPy.signalCode !== null) {
    finalize(processPy.exitCode);
  }
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
    Number.isNaN(Date.parse(dictState.startedAt)) ||
    typeof dictState.logPath !== "string" ||
    dictState.logPath.length === 0 ||
    typeof dictState.status !== "string" ||
    !setValidStatus.has(dictState.status as ExecutorRunStateStatus) ||
    (dictState.endedAt !== undefined &&
      (typeof dictState.endedAt !== "string" ||
        Number.isNaN(Date.parse(dictState.endedAt))))
  ) {
    throw new Error(`Invalid Executor run state: ${filePath}`);
  }

  return dictState as ExecutorRunState;
}

async function waitForExecutorRunStateAvailable({
  filePath,
  processPy,
  expectedRunId,
  expectedPackageName,
  expectedPackageVersion,
}: {
  filePath: string;
  processPy: ChildProcessWithoutNullStreams;
  expectedRunId: string;
  expectedPackageName: string;
  expectedPackageVersion: string;
}): Promise<ExecutorRunState> {
  const intInterval = 250;
  const intTimeout = 15 * 1000;
  let intElapsed = 0;

  while (intElapsed < intTimeout) {
    if (fs.existsSync(filePath)) {
      const dictState = readExecutorRunState({
        filePath,
        expectedRunId,
        expectedPackageName,
        expectedPackageVersion,
      });

      return dictState;
    }

    if (processPy.exitCode !== null || processPy.signalCode !== null) {
      throw new Error(
        `Python exited before publishing the initial Executor run state: ${expectedRunId}`
      );
    }

    await new Promise<void>((resolve) => setTimeout(resolve, intInterval));
    intElapsed += intInterval;
  }

  throw new Error(`Timeout waiting for the initial Executor run state: ${expectedRunId}`);
}

export function pythonCancel(
  historyId: number,
  webContentsObj: Electron.WebContents
): void {
  const processPy = dictProcessCache[String(historyId)];
  if (processPy) {
    try {
      processPy.stdin.write("Executor-terminated\n");
      processPy.stdin.end();
    } catch (e) {
      loggerMain.error(`Failed to send shutdown signal to Python process: ${e}`);
    }
    return;
  }
  loggerMain.error(`${historyId} has closed.`);

  dbUpdateHistoryDetail({
    id: historyId,
    run_end: "unknown",
    status: "cancel",
  });

  webContentsObj.send("send-from-main", "pythonResult:taskEnd");
}
