// FileName: commonFunc.ts
import { app, dialog } from "electron";
import path from "path";
import fs from "fs";
import * as os from "os";
import * as jsoncParser from "jsonc-parser";

import { DictBasicConfig, DictExecutorConfig } from "../shared/interface";

export const strDocumentsFolderPath = app.getPath("documents");
app.setPath("userData", path.join(strDocumentsFolderPath, "LiberRPA/AppData/executor/"));

export const strLiberRPAEnvPath = process.env.LiberRPA as string;
// console.log(`strLiberRPAEnvPath= ${strLiberRPAEnvPath}`);

if (!strLiberRPAEnvPath) {
  throw new Error(
    "Not found 'LiberRPA' in User Envirnment Variables, you should add it before using LiberRPA Executor."
  );
}

export const strPyEnvPath = path.join(strLiberRPAEnvPath, "envs/pyenv");

function getBasicConfigDict(): DictBasicConfig {
  const strSettingPath = path.join(strLiberRPAEnvPath, "./configFiles/basic.jsonc");

  try {
    let data = fs.readFileSync(strSettingPath, { encoding: "utf-8" });
    // console.log(data);

    const dictReplaceKeywords: { [key: string]: string } = {
      "${LiberRPA}": strLiberRPAEnvPath.replace(/\\/g, "\\\\"),
      "${UserName}": os.userInfo().username,
      "${HostName}": os.hostname(),
      "${ToolName}": "BuildinTools",
    };

    // console.log(dictReplaceKeywords);

    for (const keyName of Object.keys(dictReplaceKeywords)) {
      // Escape special regex characters in keyName
      const safeKeyName = keyName.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");

      data = data.replace(new RegExp(safeKeyName, "g"), dictReplaceKeywords[keyName]);
    }
    // console.log(data);

    const dictSettings = jsoncParser.parse(data) as DictBasicConfig;
    console.log("dictConfigBasic=", JSON.stringify(dictSettings, null, 2));
    return dictSettings;
  } catch (e) {
    throw new Error(`Error reading or parsing file: ${e}`);
  }
}

export function getExecutorConfigDict(): DictExecutorConfig {
  const strSettingPath = path.join(strLiberRPAEnvPath, "./configFiles/Executor.jsonc");

  if (!fs.existsSync(strSettingPath)) {
    // Create the Executor.jsonc if it doesn't exist.

    const dictTemp = {
      theme: "light",
      keepRdpSession: false,
      keepRdpSessionWidth: 1920,
      keepRdpSessionHeight: 1080,
      logTimeoutEnable: false,
      logTimeoutDays: 1984,
      videoTimeoutEnable: false,
      videoTimeoutDays: 30,
      videoSizeEnable: false,
      videoSizeGB: 10,
      projectLogFolderPath: path.join(
        strDocumentsFolderPath,
        "LiberRPA/OutputLog/Executor/"
      ),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };

    fs.writeFileSync(strSettingPath, JSON.stringify(dictTemp, null, 2));
  }

  try {
    const data = fs.readFileSync(strSettingPath, { encoding: "utf-8" });
    // console.log(data);

    const dictSettings = jsoncParser.parse(data) as DictExecutorConfig;
    console.log("dictConfigExecutor=", JSON.stringify(dictSettings, null, 2));
    return dictSettings;
  } catch (e) {
    throw new Error(`Error reading or parsing file: ${e}`);
  }
}

export const dictConfigBasic = getBasicConfigDict();
export const dictConfigExecutor = getExecutorConfigDict();

export function saveExecutorConfigDict(dictSettings: DictExecutorConfig): void {
  const strSettingPath = path.join(strLiberRPAEnvPath, "./configFiles/Executor.jsonc");

  try {
    const data = JSON.stringify(dictSettings, null, 2);

    fs.writeFileSync(strSettingPath, data, { encoding: "utf8" });
    // console.log("Save Executor config.");
  } catch (e) {
    throw new Error(`Error parsing or writing file: ${e}`);
  }
}

export async function selectProjectLogFolder(): Promise<string | null> {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
    title: "Select a Folder",
  });
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
}
