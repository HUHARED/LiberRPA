import { dialog } from "electron";
import fs from "fs";
import path from "path";

import type { DictExecutorConfig } from "../../shared/config";
import { ensureBoolean, ensureRecord, ensureString } from "../Common/validation";
import { strDefaultProjectLogFolderPath } from "./basicConfig";
import { strLiberRPAEnvPath } from "./environment";
import { parseJsonc } from "./jsonc";

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
    projectLogFolderPath: "",
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

  const strProjectLogFolderPath = getStringConfigValue(dictConfig, "projectLogFolderPath");
  if (strProjectLogFolderPath !== "" && !path.isAbsolute(strProjectLogFolderPath)) {
    throw new Error(
      "Executor config 'projectLogFolderPath' must be empty or an absolute path.",
    );
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
    projectLogFolderPath: strProjectLogFolderPath,
    timezone: strTimezone,
  };
}

function getExecutorConfigDict(): DictExecutorConfig {
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
    const dictSettings = validateExecutorConfig(parseJsonc(strContent, "Executor.jsonc"));

    if (dictSettings.projectLogFolderPath === strDefaultProjectLogFolderPath) {
      dictSettings.projectLogFolderPath = "";
      fs.writeFileSync(STR_EXECUTOR_CONFIG_PATH, JSON.stringify(dictSettings, null, 2), {
        encoding: "utf-8",
      });
    }

    return dictSettings;
  } catch (e: unknown) {
    throw new Error(`Error reading or parsing Executor.jsonc: ${String(e)}`, {
      cause: e,
    });
  }
}

export const dictConfigExecutor = getExecutorConfigDict();

export function getEffectiveProjectLogFolderPath(): string {
  return dictConfigExecutor.projectLogFolderPath === ""
    ? strDefaultProjectLogFolderPath
    : dictConfigExecutor.projectLogFolderPath;
}

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

export async function chooseProjectLogFolder(): Promise<string | null> {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
    title: "Select a Folder",
  });
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
}
