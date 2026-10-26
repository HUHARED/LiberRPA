// FileName: executorConfig.ts

import { dialog } from "electron";
import fs from "fs";
import path from "path";

import type { ExecutorConfig } from "../../shared/config";
import { getErrorMessage } from "../../shared/error";
import { getSystemIntlTimezone, isSupportedIntlTimezone } from "../../shared/timezone";
import { writeJsonFileAtomic } from "../Common/jsonFile";
import { ensureBoolean, ensureRecord, ensureString } from "../Common/validation";
import { strDefaultProjectLogFolderPath } from "./basicConfig";
import { strLiberRPAEnvPath } from "./environment";
import { parseJsonc } from "./jsonc";

const STR_EXECUTOR_CONFIG_PATH = path.join(
  strLiberRPAEnvPath,
  "configFiles/Executor.jsonc",
);
const ARR_EXECUTOR_CONFIG_KEY: readonly (keyof ExecutorConfig)[] = [
  "theme",
  "keepRdpSession",
  "keepRdpSessionWidth",
  "keepRdpSessionHeight",
  "logRetentionEnabled",
  "logRetentionDays",
  "videoRetentionEnabled",
  "videoRetentionDays",
  "videoStorageLimitEnabled",
  "videoStorageLimitGiB",
  "projectLogFolderPath",
  "timezone",
];
const SET_EXECUTOR_CONFIG_KEY = new Set<string>(ARR_EXECUTOR_CONFIG_KEY);

function getDefaultExecutorConfig(): ExecutorConfig {
  return {
    theme: "light",
    keepRdpSession: false,
    keepRdpSessionWidth: 1920,
    keepRdpSessionHeight: 1080,
    logRetentionEnabled: false,
    logRetentionDays: 1984,
    videoRetentionEnabled: false,
    videoRetentionDays: 30,
    videoStorageLimitEnabled: false,
    videoStorageLimitGiB: 10,
    projectLogFolderPath: "",
    timezone: getSystemIntlTimezone(),
  };
}

function getBooleanConfigValue(
  dictConfig: Record<string, unknown>,
  strKey: keyof ExecutorConfig,
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
  key: keyof ExecutorConfig;
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
  strKey: keyof ExecutorConfig,
): string {
  return ensureString(dictConfig[strKey], `Executor config '${strKey}'`);
}

export function parseExecutorConfig(value: unknown): ExecutorConfig {
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
  if (!isSupportedIntlTimezone(strTimezone)) {
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
    logRetentionEnabled: getBooleanConfigValue(dictConfig, "logRetentionEnabled"),
    logRetentionDays: getIntegerConfigValue({
      config: dictConfig,
      key: "logRetentionDays",
      min: 7,
    }),
    videoRetentionEnabled: getBooleanConfigValue(dictConfig, "videoRetentionEnabled"),
    videoRetentionDays: getIntegerConfigValue({
      config: dictConfig,
      key: "videoRetentionDays",
      min: 1,
    }),
    videoStorageLimitEnabled: getBooleanConfigValue(dictConfig, "videoStorageLimitEnabled"),
    videoStorageLimitGiB: getIntegerConfigValue({
      config: dictConfig,
      key: "videoStorageLimitGiB",
      min: 1,
    }),
    projectLogFolderPath: strProjectLogFolderPath,
    timezone: strTimezone,
  };
}

function loadExecutorConfig(): ExecutorConfig {
  if (!fs.existsSync(STR_EXECUTOR_CONFIG_PATH)) {
    const dictDefaultConfig = getDefaultExecutorConfig();
    writeJsonFileAtomic(STR_EXECUTOR_CONFIG_PATH, dictDefaultConfig);
    return dictDefaultConfig;
  }

  try {
    const strContent = fs.readFileSync(STR_EXECUTOR_CONFIG_PATH, {
      encoding: "utf-8",
    });
    const dictSettings = parseExecutorConfig(parseJsonc(strContent, "Executor.jsonc"));

    // NOTE: An exact match with the configured default means "Use Default".
    // Store an empty value so later changes to the default also apply here.
    if (dictSettings.projectLogFolderPath === strDefaultProjectLogFolderPath) {
      dictSettings.projectLogFolderPath = "";
      writeJsonFileAtomic(STR_EXECUTOR_CONFIG_PATH, dictSettings);
    }

    return dictSettings;
  } catch (e: unknown) {
    throw new Error(`Error reading or parsing Executor.jsonc: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }
}

export const dictConfigExecutor = loadExecutorConfig();

export function getEffectiveProjectLogFolderPath(): string {
  return dictConfigExecutor.projectLogFolderPath === ""
    ? strDefaultProjectLogFolderPath
    : dictConfigExecutor.projectLogFolderPath;
}

export function saveExecutorConfigDict(dictSettings: ExecutorConfig): void {
  try {
    writeJsonFileAtomic(STR_EXECUTOR_CONFIG_PATH, dictSettings);
  } catch (e: unknown) {
    throw new Error(`Error writing Executor.jsonc: ${getErrorMessage(e)}`, {
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
