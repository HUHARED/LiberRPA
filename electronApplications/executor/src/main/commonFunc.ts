// FileName: commonFunc.ts

import { app, dialog } from "electron";
import fs from "fs";
import * as jsoncParser from "jsonc-parser";
import * as os from "os";
import path from "path";

import type { DictBasicConfig, DictExecutorConfig } from "../shared/interface";
import {
  ensureBoolean,
  ensureNonEmptyString,
  ensurePositiveInteger,
  ensureRecord,
  ensureString,
} from "./validation";

export const strDocumentsFolderPath = app.getPath("documents");
app.setPath("userData", path.join(strDocumentsFolderPath, "LiberRPA/AppData/executor/"));

const strLiberRPAEnvPathValue = process.env.LiberRPA;
if (strLiberRPAEnvPathValue === undefined || strLiberRPAEnvPathValue === "") {
  throw new Error(
    "Not found 'LiberRPA' in User Environment Variables, you should add it before using LiberRPA Executor.",
  );
}
export const strLiberRPAEnvPath = strLiberRPAEnvPathValue;

export const DEFAULT_PYTHON_ENVIRONMENT_NAME = "default";
export const strPythonEnvironmentRootPath = path.join(strLiberRPAEnvPath, "envs/pyenv");
export const strDefaultPythonEnvironmentPath = path.join(
  strPythonEnvironmentRootPath,
  DEFAULT_PYTHON_ENVIRONMENT_NAME,
);

export function getPythonEnvironmentNames(): string[] {
  if (
    !fs.existsSync(strPythonEnvironmentRootPath) ||
    !fs.statSync(strPythonEnvironmentRootPath).isDirectory()
  ) {
    throw new Error(
      `Python environment folder does not exist: ${strPythonEnvironmentRootPath}`,
    );
  }

  const arrEnvironmentName = fs
    .readdirSync(strPythonEnvironmentRootPath, { withFileTypes: true })
    .filter((entryObj) => {
      if (!entryObj.isDirectory()) {
        return false;
      }

      const strPythonPath = path.join(
        strPythonEnvironmentRootPath,
        entryObj.name,
        "python.exe",
      );
      return fs.existsSync(strPythonPath) && fs.statSync(strPythonPath).isFile();
    })
    .map((entryObj) => entryObj.name);

  if (!arrEnvironmentName.includes(DEFAULT_PYTHON_ENVIRONMENT_NAME)) {
    throw new Error(
      `Default Python environment does not exist: ${strDefaultPythonEnvironmentPath}`,
    );
  }

  return arrEnvironmentName.sort((strLeft, strRight) => {
    if (strLeft === DEFAULT_PYTHON_ENVIRONMENT_NAME) {
      return -1;
    }
    if (strRight === DEFAULT_PYTHON_ENVIRONMENT_NAME) {
      return 1;
    }
    return strLeft.localeCompare(strRight);
  });
}

export function getPythonEnvironmentPath(strEnvironmentName: string): string {
  if (
    strEnvironmentName.trim() === "" ||
    strEnvironmentName !== strEnvironmentName.trim() ||
    strEnvironmentName === "." ||
    strEnvironmentName === ".." ||
    path.basename(strEnvironmentName) !== strEnvironmentName
  ) {
    throw new Error(`Invalid Python environment name: ${strEnvironmentName}`);
  }

  const strEnvironmentPath = path.join(strPythonEnvironmentRootPath, strEnvironmentName);
  const strPythonPath = path.join(strEnvironmentPath, "python.exe");
  if (!fs.existsSync(strPythonPath) || !fs.statSync(strPythonPath).isFile()) {
    throw new Error(
      `Python environment '${strEnvironmentName}' does not contain python.exe: ${strEnvironmentPath}`,
    );
  }

  return strEnvironmentPath;
}

const STR_EXECUTOR_CONFIG_PATH = path.join(
  strLiberRPAEnvPath,
  "configFiles/Executor.jsonc",
);
const ARR_EXECUTOR_CONFIG_KEY: readonly (keyof DictExecutorConfig)[] = [
  "theme",
  "keepRdpSession",
  "keepRdpSessionWidth",
  "keepRdpSessionHeight",
  "logTimeoutEnable",
  "logTimeoutDays",
  "videoTimeoutEnable",
  "videoTimeoutDays",
  "videoSizeEnable",
  "videoSizeGB",
  "projectLogFolderPath",
  "timezone",
];
const SET_EXECUTOR_CONFIG_KEY = new Set<string>(ARR_EXECUTOR_CONFIG_KEY);

function validateBasicConfig(value: unknown): DictBasicConfig {
  const dictConfig = ensureRecord(value, "Basic config");
  const intLocalServerPort = ensurePositiveInteger(
    dictConfig.localServerPort,
    "Basic config.localServerPort",
  );
  if (intLocalServerPort > 65535) {
    throw new Error("Basic config.localServerPort must be at most 65535.");
  }
  if (dictConfig.uiAnalyzerTheme !== "light" && dictConfig.uiAnalyzerTheme !== "dark") {
    throw new Error("Basic config.uiAnalyzerTheme must be 'light' or 'dark'.");
  }

  return {
    outputLogPath: ensureNonEmptyString(
      dictConfig.outputLogPath,
      "Basic config.outputLogPath",
    ),
    localServerPort: intLocalServerPort,
    uiAnalyzerTheme: dictConfig.uiAnalyzerTheme,
    uiAnalyzerMinimizeWindow: ensureBoolean(
      dictConfig.uiAnalyzerMinimizeWindow,
      "Basic config.uiAnalyzerMinimizeWindow",
    ),
    componentRepositoryPath: ensureNonEmptyString(
      dictConfig.componentRepositoryPath,
      "Basic config.componentRepositoryPath",
    ),
  };
}

function getBasicConfigDict(): DictBasicConfig {
  const strSettingPath = path.join(strLiberRPAEnvPath, "configFiles/basic.jsonc");

  try {
    let strContent = fs.readFileSync(strSettingPath, { encoding: "utf-8" });

    const dictReplaceKeyword: Record<string, string> = {
      "${LiberRPA}": strLiberRPAEnvPath.replace(/\\/g, "\\\\"),
      "${UserName}": os.userInfo().username,
      "${HostName}": os.hostname(),
      "${ToolName}": "BuiltInTools",
    };

    for (const [strKeyword, strReplacement] of Object.entries(dictReplaceKeyword)) {
      const strSafeKeyword = strKeyword.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");
      strContent = strContent.replace(new RegExp(strSafeKeyword, "g"), strReplacement);
    }

    const dictSettings = validateBasicConfig(jsoncParser.parse(strContent));
    console.log("dictConfigBasic=", JSON.stringify(dictSettings, null, 2));
    return dictSettings;
  } catch (e: unknown) {
    throw new Error(`Error reading or parsing basic.jsonc: ${String(e)}`, {
      cause: e,
    });
  }
}

function isValidTimezone(strTimezone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: strTimezone }).format();
    return true;
  } catch {
    return false;
  }
}

function getSystemTimezone(): string {
  const strTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return strTimezone !== "" && isValidTimezone(strTimezone) ? strTimezone : "UTC";
}

function getDefaultExecutorConfig(): DictExecutorConfig {
  return {
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
    projectLogFolderPath: path.join(strDocumentsFolderPath, "LiberRPA/OutputLog/Executor/"),
    timezone: getSystemTimezone(),
  };
}

function getBooleanConfigValue(
  dictConfig: Record<string, unknown>,
  strKey: keyof DictExecutorConfig,
): boolean {
  return ensureBoolean(dictConfig[strKey], `Executor config '${strKey}'`);
}

function getIntegerConfigValue({
  config,
  key,
  min,
  max,
}: {
  config: Record<string, unknown>;
  key: keyof DictExecutorConfig;
  min: number;
  max?: number;
}): number {
  const value = config[key];
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < min ||
    (max !== undefined && value > max)
  ) {
    const strRange = max === undefined ? `>= ${min}` : `between ${min} and ${max}`;
    throw new Error(`Executor config '${key}' must be an integer ${strRange}.`);
  }
  return value;
}

function getStringConfigValue(
  dictConfig: Record<string, unknown>,
  strKey: keyof DictExecutorConfig,
): string {
  return ensureString(dictConfig[strKey], `Executor config '${strKey}'`);
}

export function validateExecutorConfig(value: unknown): DictExecutorConfig {
  const dictConfig = ensureRecord(value, "Executor config");

  for (const strKey of Object.keys(dictConfig)) {
    if (!SET_EXECUTOR_CONFIG_KEY.has(strKey)) {
      throw new Error(`Unknown Executor config key: ${strKey}`);
    }
  }

  for (const strKey of ARR_EXECUTOR_CONFIG_KEY) {
    if (!Object.hasOwn(dictConfig, strKey)) {
      throw new Error(`Missing Executor config key: ${strKey}`);
    }
  }

  if (dictConfig.theme !== "light" && dictConfig.theme !== "dark") {
    throw new Error("Executor config 'theme' must be 'light' or 'dark'.");
  }

  const strTimezone = getStringConfigValue(dictConfig, "timezone");
  if (!isValidTimezone(strTimezone)) {
    throw new Error("Executor config 'timezone' must be a valid IANA time zone.");
  }

  return {
    theme: dictConfig.theme,
    keepRdpSession: getBooleanConfigValue(dictConfig, "keepRdpSession"),
    keepRdpSessionWidth: getIntegerConfigValue({
      config: dictConfig,
      key: "keepRdpSessionWidth",
      min: 480,
      max: 7680,
    }),
    keepRdpSessionHeight: getIntegerConfigValue({
      config: dictConfig,
      key: "keepRdpSessionHeight",
      min: 480,
      max: 7680,
    }),
    logTimeoutEnable: getBooleanConfigValue(dictConfig, "logTimeoutEnable"),
    logTimeoutDays: getIntegerConfigValue({
      config: dictConfig,
      key: "logTimeoutDays",
      min: 7,
    }),
    videoTimeoutEnable: getBooleanConfigValue(dictConfig, "videoTimeoutEnable"),
    videoTimeoutDays: getIntegerConfigValue({
      config: dictConfig,
      key: "videoTimeoutDays",
      min: 1,
    }),
    videoSizeEnable: getBooleanConfigValue(dictConfig, "videoSizeEnable"),
    videoSizeGB: getIntegerConfigValue({
      config: dictConfig,
      key: "videoSizeGB",
      min: 1,
    }),
    projectLogFolderPath: getStringConfigValue(dictConfig, "projectLogFolderPath"),
    timezone: strTimezone,
  };
}

export function getExecutorConfigDict(): DictExecutorConfig {
  if (!fs.existsSync(STR_EXECUTOR_CONFIG_PATH)) {
    const dictDefaultConfig = getDefaultExecutorConfig();
    fs.writeFileSync(STR_EXECUTOR_CONFIG_PATH, JSON.stringify(dictDefaultConfig, null, 2), {
      encoding: "utf-8",
    });
    return dictDefaultConfig;
  }

  try {
    const strContent = fs.readFileSync(STR_EXECUTOR_CONFIG_PATH, {
      encoding: "utf-8",
    });
    const dictSettings = validateExecutorConfig(jsoncParser.parse(strContent));
    console.log("dictConfigExecutor=", JSON.stringify(dictSettings, null, 2));
    return dictSettings;
  } catch (e: unknown) {
    throw new Error(`Error reading or parsing Executor.jsonc: ${String(e)}`, {
      cause: e,
    });
  }
}

export const dictConfigBasic = getBasicConfigDict();
export const dictConfigExecutor = getExecutorConfigDict();

export function saveExecutorConfigDict(dictSettings: DictExecutorConfig): void {
  try {
    fs.writeFileSync(STR_EXECUTOR_CONFIG_PATH, JSON.stringify(dictSettings, null, 2), {
      encoding: "utf-8",
    });
  } catch (e: unknown) {
    throw new Error(`Error writing Executor.jsonc: ${String(e)}`, {
      cause: e,
    });
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
