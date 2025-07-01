// FileName: fileFunc.ts
import { dialog } from "electron";
import { exec } from "child_process";
import path from "path";
import fs from "fs";
import AdmZip from "adm-zip";

import { strDocumentsFolderPath } from "./commonFunc";
import { DictColumns_Project_Detail_ToInsert } from "../shared/interface";

const strTempFolderPath = path.join(strDocumentsFolderPath, "LiberRPA", "Temp");
export const strExecutorPackageFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA",
  "ExecutorPackage"
);

export async function fileSelectPackageAndExtractToTempFolder(): Promise<
  DictColumns_Project_Detail_ToInsert | string
> {
  try {
    const result = await dialog.showOpenDialog({
      properties: ["openFile"],
      title: "Select an RPA Package",
      filters: [{ name: "RPA Package", extensions: ["rpa.zip"] }],
    });

    if (result.canceled) {
      return "canceled";
    }

    if (result.filePaths.length === 1) {
      // Clean temp folder to save extracted files later.
      fs.rmSync(strTempFolderPath, { recursive: true, force: true });
      fs.mkdirSync(strTempFolderPath, { recursive: true });

      const zipObj = new AdmZip(result.filePaths[0]);
      zipObj.extractAllTo(strTempFolderPath, false);

      const strJsonData = fs.readFileSync(path.join(strTempFolderPath, "project.json"), {
        encoding: "utf-8",
      });
      const dictProjectJson = JSON.parse(strJsonData);
      console.log("dictProject=", JSON.stringify(dictProjectJson, null, 2));

      if (!dictProjectJson["executorPackage"]) {
        throw new Error("Not found 'executorPackage': true in project.json");
      }

      if (
        !dictProjectJson["executorPackageName"] ||
        !dictProjectJson["executorPackageVersion"] ||
        dictProjectJson["executorPackageDescription"] === undefined
      ) {
        throw new Error(
          "executorPackageName, executorPackageVersion, executorPackageDescription should be contained in project.json"
        );
      }

      // Read data from project.flow

      const strFlowData = fs.readFileSync(path.join(strTempFolderPath, "project.flow"), {
        encoding: "utf-8",
      });
      const dictProjectFlow = JSON.parse(strFlowData);

      return {
        name: dictProjectJson["executorPackageName"] as string,
        version: dictProjectJson["executorPackageVersion"] as string,
        description: dictProjectJson["executorPackageDescription"] as string,
        timeout_min: 0,
        buildin_log_level: dictProjectFlow["logLevel"] as
          | "VERBOSE"
          | "DEBUG"
          | "INFO"
          | "WARNING"
          | "ERROR"
          | "CRITICAL",
        buildin_record_video: (dictProjectFlow["recordVideo"] as boolean) ? 1 : 0,
        buildin_stop_shortcut: (dictProjectFlow["stopShortcut"] as boolean) ? 1 : 0,
        buildin_highlight_ui: (dictProjectFlow["highlightUi"] as boolean) ? 1 : 0,
        custom_prj_args: JSON.stringify(dictProjectFlow["customPrjArgs"] as string[][]),
      };
    } else {
      //  // No "multiSelections" here means single file only, so it should not appear.
      return "Selected multiple files.";
    }
  } catch (e) {
    return `Error importing package: ${e}`;
  }
}

export async function fileDeleteTempFolder(): Promise<void> {
  fs.rmSync(strTempFolderPath, { recursive: true, force: true });
}

export async function fileDeleteExecutorPackage(
  name: string,
  version: string
): Promise<void> {
  const strExecutorPackagePath = path.join(
    strExecutorPackageFolderPath,
    `${name}_${version}`
  );
  // Delete the folder if it exists.
  fs.rmSync(strExecutorPackagePath, { recursive: true, force: true });
}

export async function fileMoveTempFilesToExecutorPackage(
  name: string,
  version: string
): Promise<void> {
  // Create the folder if it's not exist.
  fs.mkdirSync(strExecutorPackageFolderPath, { recursive: true });

  fileDeleteExecutorPackage(name, version);

  const strExecutorPackagePath = path.join(
    strExecutorPackageFolderPath,
    `${name}_${version}`
  );

  fs.renameSync(strTempFolderPath, strExecutorPackagePath);
}

export async function fileOpenFolder(folderPath: string): Promise<void> {
  if (fs.existsSync(folderPath) && fs.statSync(folderPath).isDirectory()) {
    exec(`start "" "${folderPath}"`);
    return;
  }
  throw new Error(`Folder not exists: ${folderPath}`);
}
