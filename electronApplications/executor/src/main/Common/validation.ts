import type { TypeRunHistoryStatus } from "../../shared/run";
import type { TypeRunConflictPolicy } from "../../shared/schedule";
import type { TypeCustomProjectArgs, TypeLogLevel } from "../../shared/runOptions";

export function isRecord(value: unknown): value is Record<string, unknown> {
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
  arrExpectedKey: readonly string[],
  strSourceName: string,
): Record<string, unknown> {
  const dictValue = ensureRecord(value, strSourceName);
  const setExpectedKey = new Set(arrExpectedKey);
  const arrKey = Object.keys(dictValue);
  if (
    arrKey.length !== setExpectedKey.size ||
    arrKey.some((strKey) => !setExpectedKey.has(strKey))
  ) {
    throw new Error(`${strSourceName} contains missing or unknown fields.`);
  }
  return dictValue;
}

export function ensureString(value: unknown, strSourceName: string): string {
  if (typeof value !== "string") {
    throw new Error(`${strSourceName} must be a string.`);
  }
  return value;
}

export function ensureNonEmptyString(value: unknown, strSourceName: string): string {
  const strValue = ensureString(value, strSourceName);
  if (strValue.trim() === "") {
    throw new Error(`${strSourceName} cannot be empty.`);
  }
  return strValue;
}

export function ensureBoolean(value: unknown, strSourceName: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`${strSourceName} must be a Boolean value.`);
  }
  return value;
}

export function ensureFiniteNumber(value: unknown, strSourceName: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${strSourceName} must be a finite number.`);
  }
  return value;
}

export function ensureNonNegativeInteger(value: unknown, strSourceName: string): number {
  const intValue = ensureFiniteNumber(value, strSourceName);
  if (!Number.isSafeInteger(intValue) || intValue < 0) {
    throw new Error(`${strSourceName} must be a non-negative safe integer.`);
  }
  return intValue;
}

export function ensurePositiveInteger(value: unknown, strSourceName: string): number {
  const intValue = ensureNonNegativeInteger(value, strSourceName);
  if (intValue === 0) {
    throw new Error(`${strSourceName} must be greater than 0.`);
  }
  return intValue;
}

export function ensureNullableString(value: unknown, strSourceName: string): string | null {
  if (value === null) {
    return null;
  }
  return ensureString(value, strSourceName);
}

export function ensureNullableNonNegativeInteger(
  value: unknown,
  strSourceName: string,
): number | null {
  if (value === null) {
    return null;
  }
  return ensureNonNegativeInteger(value, strSourceName);
}

export function ensureLogLevel(value: unknown, strSourceName: string): TypeLogLevel {
  switch (value) {
    case "VERBOSE":
    case "DEBUG":
    case "INFO":
    case "WARNING":
    case "ERROR":
    case "CRITICAL":
      return value;
    default:
      throw new Error(`${strSourceName} contains an unsupported log level.`);
  }
}

export function ensureRunConflictPolicy(
  value: unknown,
  strSourceName: string,
): TypeRunConflictPolicy {
  if (value === "skip" || value === "wait" || value === "concurrent") {
    return value;
  }
  throw new Error(`${strSourceName} must be 'skip', 'wait', or 'concurrent'.`);
}

export function ensureRunHistoryStatus(
  value: unknown,
  strSourceName: string,
): TypeRunHistoryStatus {
  switch (value) {
    case "running":
    case "completed":
    case "error":
    case "cancel":
    case "timeout":
    case "interrupted":
      return value;
    default:
      throw new Error(`${strSourceName} contains an unsupported status.`);
  }
}

export function ensureJsonValue(
  value: unknown,
  strSourceName: string,
  setAncestor = new Set<object>(),
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
    throw new Error(`${strSourceName} must be JSON-compatible.`);
  }
  if (setAncestor.has(value)) {
    throw new Error(`${strSourceName} cannot contain circular references.`);
  }

  setAncestor.add(value);
  try {
    if (Array.isArray(value)) {
      value.forEach((item, intIndex) => {
        ensureJsonValue(item, `${strSourceName}[${intIndex}]`, setAncestor);
      });
      return;
    }

    if (!isRecord(value)) {
      throw new Error(`${strSourceName} must be JSON-compatible.`);
    }
    for (const [strKey, item] of Object.entries(value)) {
      ensureJsonValue(item, `${strSourceName}.${strKey}`, setAncestor);
    }
  } finally {
    setAncestor.delete(value);
  }
}

export function ensureCustomProjectArgs(
  value: unknown,
  strSourceName: string,
): TypeCustomProjectArgs {
  if (!Array.isArray(value)) {
    throw new Error(`${strSourceName} must be an array.`);
  }

  const setArgumentName = new Set<string>();
  return value.map((item, intIndex) => {
    if (!Array.isArray(item) || item.length !== 2) {
      throw new Error(`${strSourceName}[${intIndex}] must be a [string, value] pair.`);
    }

    const strName = ensureNonEmptyString(item[0], `${strSourceName}[${intIndex}][0]`);
    if (strName !== strName.trim() || strName.includes("\r") || strName.includes("\n")) {
      throw new Error(
        `${strSourceName}[${intIndex}][0] must be a trimmed single-line string.`,
      );
    }
    if (setArgumentName.has(strName)) {
      throw new Error(`${strSourceName} contains a duplicate argument name: ${strName}`);
    }
    setArgumentName.add(strName);

    ensureJsonValue(item[1], `${strSourceName}[${intIndex}][1]`);
    return [strName, item[1]];
  });
}
