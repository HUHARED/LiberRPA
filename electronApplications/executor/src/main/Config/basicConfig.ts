// FileName: basicConfig.ts

import fs from "fs";
import * as os from "os";
import path from "path";

import { ensureNonEmptyString, ensureRecord } from "../Common/validation";
import { strLiberRPAEnvPath } from "./environment";
import { parseJsonc } from "./jsonc";

function getBasicConfigOutputLogPath(strToolName: "BuiltInTools" | "Executor"): string {
  const strSettingPath = path.join(strLiberRPAEnvPath, "configFiles/basic.jsonc");

  try {
    let strContent = fs.readFileSync(strSettingPath, { encoding: "utf-8" });

    const dictReplaceKeyword: Record<string, string> = {
      "${LiberRPA}": strLiberRPAEnvPath.replace(/\\/g, "\\\\"),
      "${UserName}": os.userInfo().username,
      "${HostName}": os.hostname(),
      "${ToolName}": strToolName,
    };

    for (const [strKeyword, strReplacement] of Object.entries(dictReplaceKeyword)) {
      const strSafeKeyword = strKeyword.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");
      strContent = strContent.replace(new RegExp(strSafeKeyword, "g"), strReplacement);
    }

    const dictConfig = ensureRecord(parseJsonc(strContent, "basic.jsonc"), "Basic config");
    return ensureNonEmptyString(dictConfig.outputLogPath, "Basic config.outputLogPath");
  } catch (e: unknown) {
    throw new Error(`Error reading or parsing basic.jsonc: ${String(e)}`, {
      cause: e,
    });
  }
}

export const strBuiltInToolsLogFolderPath = getBasicConfigOutputLogPath("BuiltInTools");
export const strDefaultProjectLogFolderPath = getBasicConfigOutputLogPath("Executor");
