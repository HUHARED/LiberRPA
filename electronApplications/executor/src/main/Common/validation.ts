// FileName: validation.ts

import type { Str_RunHistory_Status } from "../../shared/run";
import type { Str_RunConflictPolicy } from "../../shared/schedule";
import { INT_MAX_RUN_TIMEOUT_MIN } from "../../shared/runOptions";
import type { Arr_CustomProjectArgs, Str_LogLevel } from "../../shared/runOptions";

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

export function ensureLogLevel(value: unknown, sourceName: string): Str_LogLevel {
  switch (value) {
    case "VERBOSE":
    case "DEBUG":
    case "INFO":
    case "WARNING":
    case "ERROR":
    case "CRITICAL":
      return value;
    default:
      throw new Error(`${sourceName} contains an unsupported log level.`);
  }
}

export function ensureRunConflictPolicy(
  value: unknown,
  sourceName: string,
): Str_RunConflictPolicy {
  if (value === "skip" || value === "wait" || value === "concurrent") {
    return value;
  }
  throw new Error(`${sourceName} must be 'skip', 'wait', or 'concurrent'.`);
}

export function ensureRunHistoryStatus(
  value: unknown,
  sourceName: string,
): Str_RunHistory_Status {
  switch (value) {
    case "running":
    case "completed":
    case "error":
    case "cancel":
    case "timeout":
    case "interrupted":
      return value;
    default:
      throw new Error(`${sourceName} contains an unsupported status.`);
  }
}

function ensureJsonValue(
  value: unknown,
  sourceName: string,
  ancestorSet = new Set<object>(),
): void {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean" ||
    (typeof value === "number" && Number.isFinite(value))
  ) {
    return;
  }

  if (typeof value !== "object" || value === null) {
    throw new Error(`${sourceName} must be JSON-compatible.`);
  }
  if (ancestorSet.has(value)) {
    throw new Error(`${sourceName} cannot contain circular references.`);
  }

  ancestorSet.add(value);
  try {
    if (Array.isArray(value)) {
      value.forEach((item, intIndex) => {
        ensureJsonValue(item, `${sourceName}[${intIndex}]`, ancestorSet);
      });
      return;
    }

    if (!isRecord(value)) {
      throw new Error(`${sourceName} must be JSON-compatible.`);
    }
    for (const [strKey, item] of Object.entries(value)) {
      ensureJsonValue(item, `${sourceName}.${strKey}`, ancestorSet);
    }
  } finally {
    ancestorSet.delete(value);
  }
}

export function ensureCustomProjectArgs(
  value: unknown,
  sourceName: string,
): Arr_CustomProjectArgs {
  if (!Array.isArray(value)) {
    throw new Error(`${sourceName} must be an array.`);
  }

  const setArgumentName = new Set<string>();
  return value.map((item, intIndex) => {
    if (!Array.isArray(item) || item.length !== 2) {
      throw new Error(`${sourceName}[${intIndex}] must be a [string, value] pair.`);
    }

    const strName = ensureTrimmedSingleLineString(item[0], `${sourceName}[${intIndex}][0]`);
    if (setArgumentName.has(strName)) {
      throw new Error(`${sourceName} contains a duplicate argument name: ${strName}`);
    }
    setArgumentName.add(strName);

    ensureJsonValue(item[1], `${sourceName}[${intIndex}][1]`);
    return [strName, item[1]];
  });
}
