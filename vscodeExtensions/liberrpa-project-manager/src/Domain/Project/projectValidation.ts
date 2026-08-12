// FileName: projectValidation.ts
// IMPORTANT: Keep the Extension and Webview copies of this file synchronized.
// Synchronization is verified by scripts/checkSynchronizedFiles.mjs.
// - src/Domain/Project/projectValidation.ts
// - webview-ui/src/Domain/Project/projectValidation.ts

import { getRiskyComponentPackageNameReason } from "./riskyComponentPackageNames";

// Keep Component package names consistent with LiberRPA built-in module names.
export const REGEX_COMPONENT_PACKAGE_NAME = /^[A-Z][A-Za-z0-9]*$/;

const REGEX_INVALID_WINDOWS_FILE_OR_FOLDER_NAME_CHARACTER = /[<>:"/\\|?*]/;

const STR_COMPONENT_ID_FOR_FOLDER_NAME_VALIDATION = "00000000-0000-4000-8000-000000000000";

const SET_RESERVED_PYTHON_NAMES = new Set(["False", "None", "True"]);
const SET_RESERVED_WINDOWS_NAMES = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  "COM1",
  "COM2",
  "COM3",
  "COM4",
  "COM5",
  "COM6",
  "COM7",
  "COM8",
  "COM9",
  "LPT1",
  "LPT2",
  "LPT3",
  "LPT4",
  "LPT5",
  "LPT6",
  "LPT7",
  "LPT8",
  "LPT9",
]);

export function getWindowsFileOrFolderNameError(
  name: string,
  description: string,
): string | undefined {
  if (name.length === 0) {
    return `${description} cannot be empty.`;
  }

  if (name !== name.trim()) {
    return `${description} cannot start or end with whitespace.`;
  }

  if (REGEX_INVALID_WINDOWS_FILE_OR_FOLDER_NAME_CHARACTER.test(name)) {
    return `${description} cannot contain Windows reserved characters: ` + '<>:"/\\|?*';
  }

  if ([...name].some((character) => character.charCodeAt(0) <= 0x1f)) {
    return `${description} cannot contain ASCII control characters.`;
  }

  if (name.endsWith(".")) {
    return `${description} cannot end with a period.`;
  }

  const strNameBeforeFirstPeriod = name.split(".", 1)[0]?.toUpperCase();

  if (
    strNameBeforeFirstPeriod !== undefined &&
    SET_RESERVED_WINDOWS_NAMES.has(strNameBeforeFirstPeriod)
  ) {
    return `${description} "${name}" is reserved by Windows.`;
  }

  if (name.length > 255) {
    return `${description} cannot be longer than 255 characters.`;
  }

  return undefined;
}

export function getProjectFolderNameError(projectFolderName: string): string | undefined {
  return getWindowsFileOrFolderNameError(projectFolderName, "Project folder name");
}

export function getVersionInputError(version: string): string | undefined {
  if (version.length === 0) {
    return "Version cannot be empty.";
  }

  if (version !== version.trim()) {
    return "Version cannot start or end with whitespace.";
  }

  return undefined;
}

export function getComponentPackageNameError(packageName: string): string | undefined {
  const strWindowsNameError = getWindowsFileOrFolderNameError(packageName, "Package name");
  if (strWindowsNameError !== undefined) {
    return strWindowsNameError;
  }

  if (!REGEX_COMPONENT_PACKAGE_NAME.test(packageName)) {
    return "Package name must use PascalCase and contain only ASCII letters and digits, for example: ExcelTools.";
  }

  if (SET_RESERVED_PYTHON_NAMES.has(packageName)) {
    return `Package name cannot use the reserved Python name "${packageName}".`;
  }

  const strRepositoryFolderNameError = getWindowsFileOrFolderNameError(
    `${packageName}_${STR_COMPONENT_ID_FOR_FOLDER_NAME_VALIDATION}`,
    "Generated Component Repository folder name",
  );
  if (strRepositoryFolderNameError !== undefined) {
    return strRepositoryFolderNameError;
  }

  const strRiskyPackageNameReason = getRiskyComponentPackageNameReason(packageName);

  if (strRiskyPackageNameReason !== undefined) {
    return strRiskyPackageNameReason;
  }

  return undefined;
}

export function getDisplayNameError(displayName: string): string | undefined {
  if (displayName.trim().length === 0) {
    return "Display name cannot be empty.";
  }

  if (displayName !== displayName.trim()) {
    return "Display name cannot start or end with whitespace.";
  }

  if (displayName.includes("\r") || displayName.includes("\n")) {
    return "Display name must be a single line.";
  }

  return undefined;
}
