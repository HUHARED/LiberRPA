// FileName: typeCheck.ts
// IMPORTANT: Keep the Extension and Webview copies of this file synchronized.
// Synchronization is verified by scripts/checkSynchronizedFiles.mjs.
// - src/Common/typeCheck.ts
// - webview-ui/src/Common/typeCheck.ts

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "string");
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

export function hasExactKeys(
  value: Record<string, unknown>,
  expectedKeys: ReadonlySet<string>,
): boolean {
  const keys = Object.keys(value);
  return keys.length === expectedKeys.size && keys.every((key) => expectedKeys.has(key));
}

export function ensureExactRecord(
  value: unknown,
  expectedKeys: ReadonlySet<string>,
  sourceName: string,
): Record<string, unknown> {
  if (!isRecord(value) || !hasExactKeys(value, expectedKeys)) {
    throw new Error(`${sourceName} contains missing or unknown fields.`);
  }

  return value;
}

export function ensureString(value: unknown, sourceName: string): string {
  if (typeof value !== "string") {
    throw new Error(`${sourceName} must be a string.`);
  }

  return value;
}

export function ensureNonEmptyString(value: unknown, sourceName: string): string {
  const strValue = ensureString(value, sourceName);
  if (strValue.length === 0) {
    throw new Error(`${sourceName} cannot be empty.`);
  }
  return strValue;
}

export function ensureSha256(value: unknown, sourceName: string): string {
  const strValue = ensureNonEmptyString(value, sourceName);
  if (!/^[0-9a-f]{64}$/.test(strValue)) {
    throw new Error(`${sourceName} must be a lowercase SHA-256 value.`);
  }
  return strValue;
}

export function ensureNonNegativeInteger(value: unknown, sourceName: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`${sourceName} must be a non-negative integer.`);
  }

  return value;
}

export function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}
