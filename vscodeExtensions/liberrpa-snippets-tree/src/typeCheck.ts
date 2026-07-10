// FileName: typeCheck.ts
import type { SnippetsItem, ImportManifest } from "./interface";

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item): item is string => typeof item === "string")
  );
}

function isSnippetBody(value: unknown): value is string[] | string {
  return typeof value === "string" || isStringArray(value);
}

function hasExactKeys(
  value: UnknownRecord,
  expectedKeys: readonly string[],
): boolean {
  const actualKeys = Object.keys(value);

  return (
    actualKeys.length === expectedKeys.length &&
    actualKeys.every((key) => expectedKeys.includes(key))
  );
}

function hasRequiredKeys(value: UnknownRecord, requiredKeys: readonly string[]): boolean {
  return requiredKeys.every((key) => key in value);
}

function hasOnlyAllowedKeys(value: UnknownRecord, allowedKeys: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowedKeys.includes(key));
}

const snippetRequiredKeys = ["prefix", "body"] as const;
const snippetAllowedKeys = ["prefix", "body", "description"] as const;

function isSnippetsItem(value: unknown): value is SnippetsItem {
  if (!isRecord(value)) {
    return false;
  }

  if (
    !hasRequiredKeys(value, snippetRequiredKeys) ||
    !hasOnlyAllowedKeys(value, snippetAllowedKeys)
  ) {
    return false;
  }

  return (
    typeof value.prefix === "string" &&
    isSnippetBody(value.body) &&
    (value.description === undefined || typeof value.description === "string")
  );
}

export function isSnippetsRecord(value: unknown): value is Record<string, SnippetsItem> {
  return isRecord(value) && Object.values(value).every(isSnippetsItem);
}

const manifestKeys = ["importSource", "importOrder", "items"] as const;

function isImportItem(value: unknown): value is Record<string, string[]> {
  return isRecord(value) && Object.values(value).every((item) => isStringArray(item));
}

export function isImportManifest(value: unknown): value is ImportManifest {
  if (!isRecord(value)) {
    return false;
  }

  if (!hasExactKeys(value, manifestKeys)) {
    return false;
  }

  return (
    typeof value.importSource === "string" &&
    isStringArray(value.importOrder) &&
    isImportItem(value.items)
  );
}
