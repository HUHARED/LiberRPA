// FileName: basicConfig.ts

import fs from "fs";
import * as os from "os";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { ensureNonEmptyString, ensureRecord } from "../Common/validation";
import { strLiberRPAEnvPath } from "./environment";
import { parseJsonc } from "./jsonc";

function escapeJsonStringContent(strValue: string): string {
  return JSON.stringify(strValue).slice(1, -1);
}

function replaceBasicConfigKeywords(
  strContent: string,
  strToolName: "BuiltInTools" | "Executor",
): string {
  const dictReplaceKeyword: Record<string, string> = {
    "${LiberRPA}": escapeJsonStringContent(strLiberRPAEnvPath),
    "${UserName}": escapeJsonStringContent(os.userInfo().username),
    "${HostName}": escapeJsonStringContent(os.hostname()),
    "${ToolName}": escapeJsonStringContent(strToolName),
  };

  let strResult = strContent;
  for (const [strKeyword, strReplacement] of Object.entries(dictReplaceKeyword)) {
    strResult = strResult.replaceAll(strKeyword, () => strReplacement);
  }

  return strResult;
}

function getBasicConfigOutputLogPath(strToolName: "BuiltInTools" | "Executor"): string {
  const strSettingPath = path.join(strLiberRPAEnvPath, "configFiles/basic.jsonc");

  try {
    const strRawContent = fs.readFileSync(strSettingPath, { encoding: "utf-8" });
    const strContent = replaceBasicConfigKeywords(strRawContent, strToolName);

    const dictConfig = ensureRecord(parseJsonc(strContent, "basic.jsonc"), "Basic config");
    return ensureNonEmptyString(dictConfig.outputLogPath, "Basic config.outputLogPath");
  } catch (e: unknown) {
    throw new Error(`Error reading or parsing basic.jsonc: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }
}

export const strBuiltInToolsLogFolderPath = getBasicConfigOutputLogPath("BuiltInTools");
export const strDefaultProjectLogFolderPath = getBasicConfigOutputLogPath("Executor");
