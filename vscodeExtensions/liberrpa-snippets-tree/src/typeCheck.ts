// FileName: typeCheck.ts
import type {
  DictCatalogSnippetDefinition,
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

function isNonEmptyStringArray(value: unknown): value is string[] {
  return isStringArray(value) && value.length > 0;
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

function isPythonIdentifier(value: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value);
}

function isPythonImportSource(value: string): boolean {
  return value.split(".").every(isPythonIdentifier);
}

function isImportsBySource(value: unknown): value is DictImportsInfo {
  return (
    isRecord(value) &&
    Object.entries(value).every(
      ([source, names]) =>
        isPythonImportSource(source) &&
        isStringArray(names) &&
        names.every(isPythonIdentifier)
    )
  );
}

function isSnippetInsertionMode(value: unknown): value is "line" | "cursor" {
  return value === "line" || value === "cursor";
}

const ARR_SNIPPET_REQUIRED_KEYS = ["prefix", "body"] as const;
const ARR_SNIPPET_ALLOWED_KEYS = [
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
    !hasOnlyAllowedKeys(value, ARR_SNIPPET_ALLOWED_KEYS)
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

function isCatalogSnippetDefinition(value: unknown): value is DictCatalogSnippetDefinition {
  if (!isRecord(value)) {
    return false;
  }

  const requiredKeys = [
    "category",
    "label",
    "prefix",
    "body",
    "insertionMode",
    "description",
  ] as const;

  if (
    !hasRequiredKeys(value, requiredKeys) ||
    !hasOnlyAllowedKeys(value, ARR_SNIPPET_ALLOWED_KEYS)
  ) {
    return false;
  }

  return (
    typeof value.category === "string" &&
    typeof value.label === "string" &&
    typeof value.prefix === "string" &&
    isNonEmptyStringArray(value.body) &&
    typeof value.description === "string" &&
    (value.imports === undefined || isImportsBySource(value.imports)) &&
    isSnippetInsertionMode(value.insertionMode)
  );
}

function isCatalogSnippetDefinitions(
  value: unknown
): value is Record<string, DictCatalogSnippetDefinition> {
  return isRecord(value) && Object.values(value).every(isCatalogSnippetDefinition);
}

function isImportSourceConfig(value: unknown): value is ImportSourceConfig {
  return (
    isRecord(value) &&
    Object.keys(value).length === 1 &&
    isStringArray(value.order) &&
    value.order.every(isPythonIdentifier)
  );
}

function isImportSources(value: unknown): value is Record<string, ImportSourceConfig> {
  return (
    isRecord(value) &&
    Object.entries(value).every(
      ([source, config]) => isPythonImportSource(source) && isImportSourceConfig(config)
    )
  );
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
    isCatalogSnippetDefinitions(value.snippets)
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
