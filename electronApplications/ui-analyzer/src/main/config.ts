// FileName: config.ts
import { app } from "electron";
import path from "path";
import fs from "fs";
import * as os from "os";
import * as jsoncParser from "jsonc-parser";

import type { DictBasicConfig } from "../shared/interface";

const strLiberRPAEnvPath = process.env.LiberRPA;

export const strDocumentsFolderPath = app.getPath("documents");
app.setPath("userData", path.join(strDocumentsFolderPath, "LiberRPA/AppData/ui-analyzer/"));

function getBasicConfigDict(): DictBasicConfig {
  if (!strLiberRPAEnvPath) {
    throw new Error(
      "Not found 'LiberRPA' in User Environment Variables. Please run InitLiberRPA.exe before using LiberRPA UI Analyzer."
    );
  }

  const strSettingPath = path.join(strLiberRPAEnvPath, "./configFiles/basic.jsonc");

  try {
    let data = fs.readFileSync(strSettingPath, { encoding: "utf-8" });

    const dictReplaceKeywords: { [key: string]: string } = {
      "${LiberRPA}": strLiberRPAEnvPath.replace(/\\/g, "\\\\"),
      "${UserName}": os.userInfo().username,
      "${HostName}": os.hostname(),
      "${ToolName}": "BuiltInTools",
    };

    for (const keyName of Object.keys(dictReplaceKeywords)) {
      // Escape special regex characters in keyName
      const safeKeyName = keyName.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");

      data = data.replace(new RegExp(safeKeyName, "g"), dictReplaceKeywords[keyName]);
    }

    const dictSettings = jsoncParser.parse(data) as DictBasicConfig;
    console.log("dictConfigBasic=", JSON.stringify(dictSettings, null, 2));
    return dictSettings;
  } catch (e) {
    throw new Error(`Error reading or parsing file: ${e}`);
  }
}

export const dictConfigBasic = getBasicConfigDict();

function getToken(): string {
  const strAuthPath = path.join(strDocumentsFolderPath, "LiberRPA/WebSocketAuth.json");
  try {
    const data = fs.readFileSync(strAuthPath, { encoding: "utf-8" });

    const strToken = jsoncParser.parse(data)["uiAnalyzer"];

    if (!strToken) {
      throw new Error(`No UI Analyzer Token in ${strAuthPath}`);
    }
    return strToken;
  } catch (e: unknown) {
    throw new Error(`Error reading or parsing file: ${e}`);
  }
}

export const strToken = getToken();
