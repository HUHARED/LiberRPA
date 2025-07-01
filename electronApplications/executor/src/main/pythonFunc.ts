// FileName: pythonFunc.ts

import { spawn, ChildProcessWithoutNullStreams } from "child_process";
import path from "path";
import fs from "fs";
import moment from "moment";

import { loggerMain } from "./logger";
import { strExecutorPackageFolderPath } from "./fileFunc";
import { dbInsertHistoryDetail, dbUpdateHistoryDetail } from "./database";
import { strPyEnvPath } from "./commonFunc";
import { DictColumns_Project_Detail_Run } from "../shared/interface";

const dictProcessCache: { [key: string]: ChildProcessWithoutNullStreams } = {};
const strRunFilePath = path.join(
  strPyEnvPath,
  "Lib/site-packages/liberrpa/FlowControl/Run.py"
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

  const strProjectJsonPath = path.join(strExecutorPackagePath, "project.json");

  const boolPackageExists = fs.existsSync(strExecutorPackagePath);

  if (!boolPackageExists) {
    throw new Error(
      `${dictDetail["name"]}-${dictDetail["version"]} doesn't exist in ${strExecutorPackageFolderPath}.`
    );
  }

  /* Run python. */
  const processPy = spawn(
    path.join(strPyEnvPath, "python.exe"),
    [
      strRunFilePath,
      "--executor_args",
      JSON.stringify({
        logLevel: dictDetail["buildin_log_level"],
        recordVideo: dictDetail["buildin_record_video"],
        stopShortcut: dictDetail["buildin_stop_shortcut"],
        highlightUi: dictDetail["buildin_highlight_ui"],
        customPrjArgs: dictDetail["custom_prj_args"],
      }),
    ],
    {
      cwd: strExecutorPackagePath,
      // Follow the values in os.environ.get("PATH") and os.environ.get("PYTHONPATH") when run it in vscode.
      env: {
        PATH: [
          strPyEnvPath,
          path.join(strPyEnvPath, "Library", "mingw-w64", "bin"),
          path.join(strPyEnvPath, "Library", "usr", "bin"),
          path.join(strPyEnvPath, "Library", "bin"),
          path.join(strPyEnvPath, "Scripts"),
          path.join(strPyEnvPath, "bin"),
          process.env.PATH,
        ].join(";"),
        PYTHONPATH: [strExecutorPackagePath].join(";"),
        ...process.env,
      },
      stdio: ["pipe", "pipe", "pipe"],
    }
  );

  // Get lastStartUpTime, logPath from project.json(when "executorPackageStatus" is "running").
  await waitForProjectJsonValueRunning(strProjectJsonPath);
  loggerMain.debug("executorPackageStatus is 'running'.");

  const dictProject = readProjectJson(strProjectJsonPath);

  // Insert data into database. Only "local" source now.
  const intHistoryId = dbInsertHistoryDetail({
    scheduler_name: dictDetail.scheduler_name,
    project_source: dictDetail.project_source,
    project_id: dictDetail.id,
    project_name: dictDetail.name,
    project_version: dictDetail.version,
    run_start: `${dictProject["lastStartUpTime"].slice(0, 10)} ${dictProject[
      "lastStartUpTime"
    ].slice(11, 13)}:${dictProject["lastStartUpTime"].slice(13, 15)}:${dictProject[
      "lastStartUpTime"
    ].slice(15, 17)}`,
    status: dictProject["executorPackageStatus"] as "running",
    log_path: dictProject["logPath"],
  })["lastInsertRowid"];

  dictProcessCache[String(intHistoryId)] = processPy;

  // Set timeout.
  let boolTimeout = false;
  let timeoutId: NodeJS.Timeout | undefined;
  if (dictDetail.timeout_min !== 0) {
    loggerMain.info(`Set timeout: ${dictDetail.timeout_min}`);
    timeoutId = setTimeout(() => {
      // Is the Python program is running.
      if (processPy) {
        loggerMain.info(
          `Timeout reached. Killing ${dictDetail["name"]}-${dictDetail["version"]}`
        );
        try {
          processPy.stdin.write("Executor-terminated\n");
          processPy.stdin.end();
        } catch (e) {
          loggerMain.error(`Failed to send shutdown signal to Python process: ${e}`);
        }

        boolTimeout = true;
      }
    }, dictDetail.timeout_min * 60 * 1000);
  }

  /* When the Python process closed. */
  processPy.on("close", (code) => {
    loggerMain.info(
      `${dictDetail["name"]}-${dictDetail["version"]} exited with code ${code}`
    );

    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    // Get data from project.json, modify executorPackageStatus if it's "running" or "terminated"

    const dictProject = readProjectJson(strProjectJsonPath);
    if (dictProject["executorPackageStatus"] === "terminated" && boolTimeout) {
      dictProject["executorPackageStatus"] = "timeout";
    } else if (dictProject["executorPackageStatus"] === "terminated") {
      dictProject["executorPackageStatus"] = "cancel";
    } else if (dictProject["executorPackageStatus"] === "running") {
      dictProject["executorPackageStatus"] = "completed";
    }
    fs.writeFileSync(strProjectJsonPath, JSON.stringify(dictProject, null, 4), {
      encoding: "utf-8",
    });

    // Update database
    dbUpdateHistoryDetail({
      id: intHistoryId as number,
      run_end: moment(new Date()).format("YYYY-MM-DD HH:mm:ss"),
      status: dictProject["executorPackageStatus"] as
        | "cancel"
        | "completed"
        | "error"
        | "timeout",
    });

    // Remove cache.
    delete dictProcessCache[String(intHistoryId)];

    webContentsObj.send("send-from-main", "pythonResult:taskEnd");
  });

  // End the function but the "close" listener will still run until the Python process object deleted.
  return;
}

function readProjectJson(filePath: string): { [key: string]: string } {
  const strContent = fs.readFileSync(filePath, { encoding: "utf-8" });
  const dictProject: { [key: string]: string } = JSON.parse(strContent);
  console.log("dictProject=", JSON.stringify(dictProject));

  return dictProject;
}

async function waitForProjectJsonValueRunning(filePath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const intInterval = 1000;
    let intElapsed = 0;

    const intervalId = setInterval(() => {
      const dictProject = readProjectJson(filePath);

      if (dictProject["executorPackageStatus"] === "running") {
        clearInterval(intervalId);
        resolve();
      }
      intElapsed += intInterval;
      if (intElapsed >= 15 * 1000) {
        clearInterval(intervalId);
        reject(new Error("Timeout waiting for executorPackageStatus to be running"));
      }
    }, intInterval);
  });
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
    id: historyId as number,
    run_end: "unknown",
    status: "cancel",
  });

  webContentsObj.send("send-from-main", "pythonResult:taskEnd");
}
