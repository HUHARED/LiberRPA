// FileName: typeCheck.ts
import type {
  DictSnippetFavoriteFile,
  ImportSourceConfig,
  DictImportsInfo,
  DictSnippetCatalogFile,
  DictSnippetDefinition,
} from "./interface";

type UnknownRecord = Record<string, unknown>;

export function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isSnippetBody(value: unknown): value is string[] | string {
  return typeof value === "string" || isStringArray(value);
}

function hasRequiredKeys(value: UnknownRecord, requiredKeys: readonly string[]): boolean {
  return requiredKeys.every((key) => key in value);
}

function hasOnlyAllowedKeys(value: UnknownRecord, allowedKeys: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowedKeys.includes(key));
}

function isImportsBySource(value: unknown): value is DictImportsInfo {
  return isRecord(value) && Object.values(value).every(isStringArray);
}

function isSnippetInsertionMode(value: unknown): value is "line" | "cursor" {
  return value === "line" || value === "cursor";
}

const ARR_SNIPPET_REQUIRED_KEYS = ["prefix", "body"] as const;
const ARR_SNIPPET_ALLOWED_KEYSs = [
  "category",
  "label",
  "prefix",
  "body",
  "description",
  "imports",
  "insertionMode",
] as const;

function isSnippetDefinition(value: unknown): value is DictSnippetDefinition {
  if (!isRecord(value)) {
    return false;
  }

  if (
    !hasRequiredKeys(value, ARR_SNIPPET_REQUIRED_KEYS) ||
    !hasOnlyAllowedKeys(value, ARR_SNIPPET_ALLOWED_KEYSs)
  ) {
    return false;
  }

  return (
    (value.category === undefined || typeof value.category === "string") &&
    (value.label === undefined || typeof value.label === "string") &&
    typeof value.prefix === "string" &&
    isSnippetBody(value.body) &&
    (value.description === undefined || typeof value.description === "string") &&
    (value.imports === undefined || isImportsBySource(value.imports)) &&
    (value.insertionMode === undefined || isSnippetInsertionMode(value.insertionMode))
  );
}

function isSnippetDefinitions(
  value: unknown
): value is Record<string, DictSnippetDefinition> {
  return isRecord(value) && Object.values(value).every(isSnippetDefinition);
}

function isImportSourceConfig(value: unknown): value is ImportSourceConfig {
  return isRecord(value) && Object.keys(value).length === 1 && isStringArray(value.order);
}

function isImportSources(value: unknown): value is Record<string, ImportSourceConfig> {
  return isRecord(value) && Object.values(value).every(isImportSourceConfig);
}

export function isSnippetCatalog(value: unknown): value is DictSnippetCatalogFile {
  if (!isRecord(value)) {
    return false;
  }

  const expectedKeys = [
    "schemaVersion",
    "categoryOrder",
    "importSources",
    "snippets",
  ] as const;

  return (
    hasRequiredKeys(value, expectedKeys) &&
    hasOnlyAllowedKeys(value, expectedKeys) &&
    value.schemaVersion === 1 &&
    isStringArray(value.categoryOrder) &&
    isImportSources(value.importSources) &&
    isSnippetDefinitions(value.snippets) &&
    Object.values(value.snippets).every(
      (snippet) => typeof snippet.category === "string" && typeof snippet.label === "string"
    )
  );
}

export function isFavoriteSnippetsFile(value: unknown): value is DictSnippetFavoriteFile {
  if (!isRecord(value)) {
    return false;
  }

  const expectedKeys = ["schemaVersion", "snippets"] as const;

  return (
    hasRequiredKeys(value, expectedKeys) &&
    hasOnlyAllowedKeys(value, expectedKeys) &&
    value.schemaVersion === 1 &&
    isSnippetDefinitions(value.snippets)
  );
}
