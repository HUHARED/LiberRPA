// FileName: validation.ts

import { RunSource, RunStatus } from "../../shared/run";
import {
  INT_MAX_RETRY_COUNT,
  INT_MAX_RUN_TIMEOUT_MIN,
  LogLevel,
  RunConflictPolicy,
} from "../../shared/runOptions";
import type { CustomProjectArgs } from "../../shared/runOptions";

const INT_MAX_DESCRIPTION_LENGTH = 2000;
const INT_MAX_VERSION_SUMMARY_LENGTH = 500;
const INT_MAX_CUSTOM_ARGUMENT_COUNT = 100;
export const INT_MAX_CUSTOM_ARGUMENT_JSON_BYTES = 64 * 1024;
const INT_MAX_JSON_DEPTH = 64;
const SET_RESERVED_WINDOWS_NAME = new Set([
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
const REGEX_INVALID_WINDOWS_NAME_CHARACTER = /[<>:"/\\|?*]/;

function isRecord(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const objPrototype = Object.getPrototypeOf(value);
  return objPrototype === Object.prototype || objPrototype === null;
}

export function ensureRecord(
  value: unknown,
  strSourceName: string,
): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new Error(`${strSourceName} must be an object.`);
  }
  return value;
}

export function ensureExactRecord(
  value: unknown,
  expectedKeyArr: readonly string[],
  sourceName: string,
): Record<string, unknown> {
  const dictValue = ensureRecord(value, sourceName);
  const setExpectedKey = new Set(expectedKeyArr);
  const arrKey = Object.keys(dictValue);
  if (
    arrKey.length !== setExpectedKey.size ||
    arrKey.some((strKey) => !setExpectedKey.has(strKey))
  ) {
    throw new Error(`${sourceName} contains missing or unknown fields.`);
  }
  return dictValue;
}

export function ensureString(value: unknown, sourceName: string): string {
  if (typeof value !== "string") {
    throw new Error(`${sourceName} must be a string.`);
  }
  if (value.includes("\0")) {
    throw new Error(`${sourceName} cannot contain null characters.`);
  }
  if (/[\uD800-\uDFFF]/u.test(value)) {
    throw new Error(`${sourceName} must contain valid Unicode text.`);
  }
  return value;
}

export function ensureNonEmptyString(value: unknown, sourceName: string): string {
  const strValue = ensureString(value, sourceName);
  if (strValue.trim() === "") {
    throw new Error(`${sourceName} cannot be empty.`);
  }
  return strValue;
}

export function ensureTrimmedSingleLineString(
  value: unknown,
  sourceName: string,
  boolAllowEmpty = false,
): string {
  const strValue = ensureString(value, sourceName);
  if (!boolAllowEmpty && strValue.length === 0) {
    throw new Error(`${sourceName} cannot be empty.`);
  }
  if (strValue !== strValue.trim()) {
    throw new Error(`${sourceName} cannot start or end with whitespace.`);
  }
  if (strValue.includes("\r") || strValue.includes("\n")) {
    throw new Error(`${sourceName} must be a single line.`);
  }
  return strValue;
}

function ensureTextLength(value: string, sourceName: string, maxLength: number): string {
  if ([...value].length > maxLength) {
    throw new Error(`${sourceName} cannot exceed ${maxLength} characters.`);
  }
  return value;
}

export function ensurePackageDescription(value: unknown, sourceName: string): string {
  return ensureTextLength(
    ensureString(value, sourceName),
    sourceName,
    INT_MAX_DESCRIPTION_LENGTH,
  );
}

export function ensureVersionSummary(value: unknown, sourceName: string): string {
  return ensureTextLength(
    ensureTrimmedSingleLineString(value, sourceName, true),
    sourceName,
    INT_MAX_VERSION_SUMMARY_LENGTH,
  );
}

export function getWindowsFolderNameError(name: string): string | undefined {
  if (name.length === 0 || name !== name.trim()) {
    return "Folder name cannot be empty or start/end with whitespace.";
  }
  if (REGEX_INVALID_WINDOWS_NAME_CHARACTER.test(name)) {
    return "Folder name contains Windows reserved characters.";
  }
  if ([...name].some((strCharacter) => strCharacter.charCodeAt(0) <= 0x1f)) {
    return "Folder name contains ASCII control characters.";
  }
  if (name.endsWith(".")) {
    return "Folder name cannot end with a period.";
  }
  const strBaseName = name.split(".", 1)[0]?.toUpperCase();
  if (strBaseName !== undefined && SET_RESERVED_WINDOWS_NAME.has(strBaseName)) {
    return `Folder name '${name}' is reserved by Windows.`;
  }
  if (name.length > 255) {
    return "Folder name cannot be longer than 255 UTF-16 code units.";
  }
  return undefined;
}

export function ensurePythonEnvironmentName(value: unknown, sourceName: string): string {
  const strValue = ensureString(value, sourceName);
  const strError = getWindowsFolderNameError(strValue);
  if (strError !== undefined) {
    throw new Error(`${sourceName}: ${strError}`);
  }
  return strValue;
}

export function ensureBoolean(value: unknown, sourceName: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`${sourceName} must be a Boolean value.`);
  }
  return value;
}

function ensureFiniteNumber(value: unknown, sourceName: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${sourceName} must be a finite number.`);
  }
  return value;
}

export function ensureNonNegativeInteger(value: unknown, sourceName: string): number {
  const intValue = ensureFiniteNumber(value, sourceName);
  if (!Number.isSafeInteger(intValue) || intValue < 0) {
    throw new Error(`${sourceName} must be a non-negative safe integer.`);
  }
  return intValue;
}

export function ensurePositiveInteger(value: unknown, sourceName: string): number {
  const intValue = ensureNonNegativeInteger(value, sourceName);
  if (intValue === 0) {
    throw new Error(`${sourceName} must be greater than 0.`);
  }
  return intValue;
}

export function ensureRetryCount(value: unknown, sourceName: string): number {
  const intValue = ensureNonNegativeInteger(value, sourceName);
  if (intValue > INT_MAX_RETRY_COUNT) {
    throw new Error(`${sourceName} must be between 0 and ${INT_MAX_RETRY_COUNT}.`);
  }
  return intValue;
}

export function ensureRunTimeoutMinutes(value: unknown, sourceName: string): number {
  const intValue = ensureNonNegativeInteger(value, sourceName);
  if (intValue > INT_MAX_RUN_TIMEOUT_MIN) {
    throw new Error(
      `${sourceName} cannot exceed ${String(INT_MAX_RUN_TIMEOUT_MIN)} minutes.`,
    );
  }
  return intValue;
}

export function ensureNullableString(value: unknown, sourceName: string): string | null {
  if (value === null) {
    return null;
  }
  return ensureString(value, sourceName);
}

export function ensureNullableNonNegativeInteger(
  value: unknown,
  sourceName: string,
): number | null {
  if (value === null) {
    return null;
  }
  return ensureNonNegativeInteger(value, sourceName);
}

export function ensureLogLevel(value: unknown, sourceName: string): LogLevel {
  switch (value) {
    case LogLevel.Verbose:
    case LogLevel.Debug:
    case LogLevel.Info:
    case LogLevel.Warning:
    case LogLevel.Error:
    case LogLevel.Critical:
      return value;
    default:
      throw new Error(`${sourceName} contains an unsupported log level.`);
  }
}

export function ensureRunConflictPolicy(
  value: unknown,
  sourceName: string,
): RunConflictPolicy {
  if (
    value === RunConflictPolicy.Skip ||
    value === RunConflictPolicy.Wait ||
    value === RunConflictPolicy.Concurrent
  ) {
    return value;
  }
  throw new Error(`${sourceName} must be 'skip', 'wait', or 'concurrent'.`);
}

export function ensureRunSource(value: unknown, sourceName: string): RunSource {
  if (value === RunSource.Local || value === RunSource.Console) return value;
  throw new Error(`${sourceName} contains an unsupported Run source.`);
}

export function ensureRunHistoryStatus(value: unknown, sourceName: string): RunStatus {
  switch (value) {
    case RunStatus.Running:
    case RunStatus.Completed:
    case RunStatus.Error:
    case RunStatus.Canceled:
    case RunStatus.TimedOut:
    case RunStatus.Interrupted:
    case RunStatus.Unknown:
      return value;
    default:
      throw new Error(`${sourceName} contains an unsupported status.`);
  }
}

export function ensureJsonValue(
  value: unknown,
  sourceName: string,
  depth = 0,
  ancestorSet = new Set<object>(),
): void {
  if (depth > INT_MAX_JSON_DEPTH) {
    throw new Error(`${sourceName} cannot exceed ${INT_MAX_JSON_DEPTH} levels of nesting.`);
  }
  if (value === null || typeof value === "boolean") {
    return;
  }
  if (typeof value === "string") {
    ensureString(value, sourceName);
    return;
  }
  if (typeof value === "number") {
    if (
      !Number.isFinite(value) ||
      (Number.isInteger(value) && !Number.isSafeInteger(value))
    ) {
      throw new Error(`${sourceName} must contain finite numbers and safe integers.`);
    }
    return;
  }
  if (typeof value !== "object") {
    throw new Error(`${sourceName} must be JSON-compatible.`);
  }
  if (ancestorSet.has(value)) {
    throw new Error(`${sourceName} cannot contain circular references.`);
  }

  ancestorSet.add(value);
  try {
    if (Array.isArray(value)) {
      for (let intIndex = 0; intIndex < value.length; intIndex++) {
        ensureJsonValue(
          value[intIndex],
          `${sourceName}[${intIndex}]`,
          depth + 1,
          ancestorSet,
        );
      }
      return;
    }

    if (!isRecord(value)) {
      throw new Error(`${sourceName} must be JSON-compatible.`);
    }
    for (const [strKey, item] of Object.entries(value)) {
      ensureString(strKey, `${sourceName} object key`);
      ensureJsonValue(item, `${sourceName}.${strKey}`, depth + 1, ancestorSet);
    }
  } finally {
    ancestorSet.delete(value);
  }
}

export function ensureCustomProjectArgs(
  value: unknown,
  sourceName: string,
): CustomProjectArgs {
  if (!Array.isArray(value)) {
    throw new Error(`${sourceName} must be an array.`);
  }
  if (value.length > INT_MAX_CUSTOM_ARGUMENT_COUNT) {
    throw new Error(`${sourceName} cannot exceed ${INT_MAX_CUSTOM_ARGUMENT_COUNT} pairs.`);
  }
  // Count depth from the complete ordered list, including its [name, value] pairs.
  ensureJsonValue(value, sourceName);
  const arrArgument: CustomProjectArgs = value.map((item, intIndex) => {
    if (!Array.isArray(item) || item.length !== 2) {
      throw new Error(`${sourceName}[${intIndex}] must be a [string, value] pair.`);
    }
    const strName = ensureString(item[0], `${sourceName}[${intIndex}][0]`);
    return [strName, item[1]];
  });
  if (
    Buffer.byteLength(JSON.stringify(arrArgument), "utf8") >
    INT_MAX_CUSTOM_ARGUMENT_JSON_BYTES
  ) {
    throw new Error(`${sourceName} exceeds the 64 KiB JSON limit.`);
  }
  return arrArgument;
}
