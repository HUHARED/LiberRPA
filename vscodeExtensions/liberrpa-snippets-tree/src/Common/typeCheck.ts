// FileName: typeCheck.ts

export type UnknownRecord = Record<string, unknown>;

export function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

export function hasRequiredKeys(
  value: UnknownRecord,
  requiredKeys: readonly string[],
): boolean {
  return requiredKeys.every((key) => key in value);
}

export function hasOnlyAllowedKeys(
  value: UnknownRecord,
  allowedKeys: readonly string[],
): boolean {
  return Object.keys(value).every((key) => allowedKeys.includes(key));
}
