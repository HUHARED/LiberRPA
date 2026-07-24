// FileName: projectValidation.ts
// Keep this file synchronized with:
// - src/projectValidation.ts
// - webview-ui/src/projectValidation.ts

import { getRiskyComponentPackageNameReason } from "./riskyComponentPackageNames";

// Use this kind of pattern to ensure Components have the same naming conversation like LiberRPA built-in modules.
export const REGEX_COMPONENT_PACKAGE_NAME = /^[A-Z][A-Za-z0-9]*$/;

const SET_INVALID_PYTHON_IDENTIFIERS = new Set(["False", "None", "True"]);
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

export function getProjectFolderNameError(projectName: string): string | undefined {
  if (projectName.length === 0) {
    return "Project folder name cannot be empty.";
  }

  if (projectName !== projectName.trim()) {
    return "Project folder name cannot start or end with whitespace.";
  }

  if (/[<>:"/\\|?*]/.test(projectName)) {
    return `Project folder name cannot contain Windows reserved characters: ${'<>:"/\\|?*'}`;
  }

  if ([...projectName].some((character) => character.charCodeAt(0) <= 0x1f)) {
    return "Project folder name cannot contain ASCII control characters.";
  }

  if (projectName.endsWith(".")) {
    return "Project folder name cannot end with a period.";
  }

  const nameBeforeFirstPeriod = projectName.split(".", 1)[0]?.toUpperCase();
  if (
    nameBeforeFirstPeriod !== undefined &&
    SET_RESERVED_WINDOWS_NAMES.has(nameBeforeFirstPeriod)
  ) {
    return `Project folder name "${projectName}" is reserved by Windows.`;
  }

  if (projectName.length > 255) {
    return "Project folder name cannot be longer than 255 characters.";
  }

  return undefined;
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
  if (!REGEX_COMPONENT_PACKAGE_NAME.test(packageName)) {
    return "Package name must use PascalCase and contain only ASCII letters and digits, for example: ExcelTools.";
  }

  if (SET_INVALID_PYTHON_IDENTIFIERS.has(packageName)) {
    return `Package name cannot be the Python keyword "${packageName}".`;
  }

  if (SET_RESERVED_WINDOWS_NAMES.has(packageName.toUpperCase())) {
    return `Package name "${packageName}" is reserved by Windows.`;
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
