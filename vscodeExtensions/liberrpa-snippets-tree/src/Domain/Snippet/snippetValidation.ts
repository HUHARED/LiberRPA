// FileName: snippetValidation.ts

import {
  isRecord,
  isStringArray,
  hasRequiredKeys,
  hasOnlyAllowedKeys,
} from "../../Common/typeCheck";
import type {
  SnippetInsertionMode,
  DictImportsInfo,
  DictImportSourceConfig,
  DictSnippetDefinition,
  DictCatalogSnippetDefinition,
  DictSnippetCatalogFile,
  DictSnippetFavoriteFile,
  DictSnippetNodeCommandArg,
} from "./snippetTypes";

function isNonEmptyStringArray(value: unknown): value is string[] {
  return isStringArray(value) && value.length > 0;
}

function isSnippetBody(value: unknown): value is string[] | string {
  return typeof value === "string" || isStringArray(value);
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
        names.every(isPythonIdentifier),
    )
  );
}

function isSnippetInsertionMode(value: unknown): value is SnippetInsertionMode {
  return value === "line" || value === "cursor";
}

const ARR_SNIPPET_REQUIRED_KEY = ["prefix", "body"] as const;
const ARR_SNIPPET_ALLOWED_KEY = [
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
    !hasRequiredKeys(value, ARR_SNIPPET_REQUIRED_KEY) ||
    !hasOnlyAllowedKeys(value, ARR_SNIPPET_ALLOWED_KEY)
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
  value: unknown,
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
    !hasOnlyAllowedKeys(value, ARR_SNIPPET_ALLOWED_KEY)
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
  value: unknown,
): value is Record<string, DictCatalogSnippetDefinition> {
  return isRecord(value) && Object.values(value).every(isCatalogSnippetDefinition);
}

const ARR_IMPORT_SOURCE_CONFIG_REQUIRED_KEY = ["order"] as const;
const ARR_IMPORT_SOURCE_CONFIG_ALLOWED_KEY = ["order", "aliasMode"] as const;

function isImportSourceConfig(value: unknown): value is DictImportSourceConfig {
  if (!isRecord(value)) {
    return false;
  }

  if (
    !hasRequiredKeys(value, ARR_IMPORT_SOURCE_CONFIG_REQUIRED_KEY) ||
    !hasOnlyAllowedKeys(value, ARR_IMPORT_SOURCE_CONFIG_ALLOWED_KEY)
  ) {
    return false;
  }

  return (
    isStringArray(value.order) &&
    value.order.every(isPythonIdentifier) &&
    (value.aliasMode === undefined || value.aliasMode === "source_module")
  );
}

function isImportSources(value: unknown): value is Record<string, DictImportSourceConfig> {
  return (
    isRecord(value) &&
    Object.entries(value).every(([source, config]) => {
      if (!isPythonImportSource(source) || !isImportSourceConfig(config)) {
        return false;
      }

      // source_module derives aliases as <source>_<module>, so its source
      // must be one Python identifier rather than a dotted import path.
      return config.aliasMode !== "source_module" || isPythonIdentifier(source);
    })
  );
}

export function isSnippetCatalogFile(value: unknown): value is DictSnippetCatalogFile {
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
    new Set(value.categoryOrder).size === value.categoryOrder.length &&
    isImportSources(value.importSources) &&
    isCatalogSnippetDefinitions(value.snippets)
  );
}

export function isFavoriteSnippetFile(value: unknown): value is DictSnippetFavoriteFile {
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

export function isSnippetNodeCommandArg(
  value: unknown,
): value is DictSnippetNodeCommandArg {
  if (!isRecord(value)) {
    return false;
  }

  const expectedKeys = ["title", "body", "imports", "insertionMode"] as const;

  return (
    hasRequiredKeys(value, expectedKeys) &&
    hasOnlyAllowedKeys(value, expectedKeys) &&
    typeof value.title === "string" &&
    isNonEmptyStringArray(value.body) &&
    isImportsBySource(value.imports) &&
    isSnippetInsertionMode(value.insertionMode)
  );
}
