// FileName: config.ts

import fs from "fs";
import * as os from "os";
import path from "path";
import * as jsoncParser from "jsonc-parser";

import { getErrorMessage } from "../shared/error";
import type { UiAnalyzerInitialization } from "../shared/interface";

export interface UiAnalyzerMainConfig {
  documentsFolderPath: string;
  outputLogPath: string;
  initialization: UiAnalyzerInitialization;
}

function parseJsonc(strContent: string, strSourceName: string): unknown {
  const arrParseError: jsoncParser.ParseError[] = [];
  const value = jsoncParser.parse(strContent, arrParseError);

  if (arrParseError.length !== 0) {
    const firstError = arrParseError[0];
    throw new Error(
      `${strSourceName} contains invalid JSONC at offset ${String(firstError.offset)}.`,
    );
  }

  return value;
}

function ensureRecord(value: unknown, strSourceName: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${strSourceName} must be an object.`);
  }

  return value as Record<string, unknown>;
}

function ensureNonEmptyString(value: unknown, strSourceName: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${strSourceName} must be a non-empty string.`);
  }

  return value;
}

function ensureLocalServerPort(value: unknown): number {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < 1 ||
    value > 65_535
  ) {
    throw new Error("basic.jsonc.localServerPort must be an integer from 1 to 65535.");
  }

  return value;
}

function ensureUiAnalyzerTheme(value: unknown): "light" | "dark" {
  if (value !== "light" && value !== "dark") {
    throw new Error('basic.jsonc.uiAnalyzerTheme must be either "light" or "dark".');
  }

  return value;
}

function ensureBoolean(value: unknown, strSourceName: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`${strSourceName} must be a Boolean value.`);
  }

  return value;
}

function escapeJsonStringContent(strValue: string): string {
  return JSON.stringify(strValue).slice(1, -1);
}

function replaceBasicConfigKeywords(strContent: string, strLiberRPAPath: string): string {
  const dictReplaceKeyword: Record<string, string> = {
    "${LiberRPA}": escapeJsonStringContent(strLiberRPAPath),
    "${UserName}": escapeJsonStringContent(os.userInfo().username),
    "${HostName}": escapeJsonStringContent(os.hostname()),
    "${ToolName}": "BuiltInTools",
  };

  let strResult = strContent;
  for (const [strKeyword, strReplacement] of Object.entries(dictReplaceKeyword)) {
    strResult = strResult.replaceAll(strKeyword, () => strReplacement);
  }

  return strResult;
}

function loadBasicConfig(strLiberRPAPath: string): {
  outputLogPath: string;
  localServerPort: number;
  theme: "light" | "dark";
  minimizeWindow: boolean;
} {
  const strBasicConfigPath = path.join(strLiberRPAPath, "configFiles", "basic.jsonc");

  try {
    const strRawContent = fs.readFileSync(strBasicConfigPath, { encoding: "utf-8" });
    const strContent = replaceBasicConfigKeywords(strRawContent, strLiberRPAPath);
    const dictConfig = ensureRecord(
      parseJsonc(strContent, strBasicConfigPath),
      "Basic config",
    );

    return {
      outputLogPath: ensureNonEmptyString(
        dictConfig.outputLogPath,
        "basic.jsonc.outputLogPath",
      ),
      localServerPort: ensureLocalServerPort(dictConfig.localServerPort),
      theme: ensureUiAnalyzerTheme(dictConfig.uiAnalyzerTheme),
      minimizeWindow: ensureBoolean(
        dictConfig.uiAnalyzerMinimizeWindow,
        "basic.jsonc.uiAnalyzerMinimizeWindow",
      ),
    };
  } catch (e: unknown) {
    throw new Error(`Failed to load ${strBasicConfigPath}: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }
}

function loadUiAnalyzerToken(strDocumentsFolderPath: string): string {
  const strAuthPath = path.join(strDocumentsFolderPath, "LiberRPA", "WebSocketAuth.json");

  try {
    const strContent = fs.readFileSync(strAuthPath, { encoding: "utf-8" });
    const dictAuth = ensureRecord(parseJsonc(strContent, strAuthPath), "WebSocket auth");
    return ensureNonEmptyString(dictAuth.uiAnalyzer, "WebSocketAuth.json.uiAnalyzer");
  } catch (e: unknown) {
    throw new Error(`Failed to load ${strAuthPath}: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }
}

export function loadUiAnalyzerMainConfig(
  strDocumentsFolderPath: string,
): UiAnalyzerMainConfig {
  const strLiberRPAPath = process.env.LiberRPA;
  if (strLiberRPAPath === undefined || strLiberRPAPath.trim() === "") {
    throw new Error(
      "Not found 'LiberRPA' in User Environment Variables. Please run InitLiberRPA.exe before using LiberRPA UI Analyzer.",
    );
  }

  const dictBasicConfig = loadBasicConfig(strLiberRPAPath);

  return {
    documentsFolderPath: strDocumentsFolderPath,
    outputLogPath: dictBasicConfig.outputLogPath,
    initialization: {
      localServerPort: dictBasicConfig.localServerPort,
      theme: dictBasicConfig.theme,
      minimizeWindow: dictBasicConfig.minimizeWindow,
      token: loadUiAnalyzerToken(strDocumentsFolderPath),
    },
  };
}
