// FileName: snippetRepository.ts

import type {
  DictImportsInfo,
  DictImportSourceConfig,
  DictSnippetFavoriteFile,
  Info_LoadedSnippetCatalog,
  Info_Snippet,
  Info_SnippetRepository,
  Info_SnippetRepositoryBuildResult,
} from "./snippetTypes";

const STR_FAVORITE_CATEGORY = "Favorite";

function compareNamesCaseInsensitive(firstName: string, secondName: string): number {
  const intInsensitiveComparison = firstName
    .toLowerCase()
    .localeCompare(secondName.toLowerCase());

  return intInsensitiveComparison !== 0
    ? intInsensitiveComparison
    : firstName.localeCompare(secondName);
}

function normalizeSnippetBody(body: string[] | string): string[] {
  const arrLine = Array.isArray(body) ? body : body.split(/\r?\n/);
  return arrLine.map((line) => line.replace(/\t/g, "    "));
}

function normalizeImports(imports: DictImportsInfo | undefined): DictImportsInfo {
  if (imports === undefined) {
    return {};
  }

  const dictResult: DictImportsInfo = {};

  for (const [source, importNameList] of Object.entries(imports)) {
    dictResult[source] = [...new Set(importNameList)];
  }

  return dictResult;
}

function cloneImportSourceConfig(config: DictImportSourceConfig): DictImportSourceConfig {
  return {
    order: [...config.order],
    ...(config.aliasMode === undefined ? {} : { aliasMode: config.aliasMode }),
  };
}

function addWarningForUnknownImportSources(
  snippet: Info_Snippet,
  knownImportSourceSet: ReadonlySet<string>,
  warningList: string[],
): void {
  const listUnknownSource = Object.keys(snippet.imports).filter(
    (source) => !knownImportSourceSet.has(source),
  );

  if (listUnknownSource.length === 0) {
    return;
  }

  warningList.push(
    `Snippet ${snippet.title} uses import sources without an order ` +
      `configuration: ${listUnknownSource.join(", ")}.`,
  );
}

function addCatalogToRepository(
  loadedCatalog: Info_LoadedSnippetCatalog,
  snippetByCategory: Record<string, Info_Snippet[]>,
  snippetById: Record<string, Info_Snippet>,
  importSource: Record<string, DictImportSourceConfig>,
  categoryOrder: string[],
  snippetOwnerMap: Map<string, string>,
  importSourceOwnerMap: Map<string, string>,
): void {
  for (const [source, config] of Object.entries(loadedCatalog.catalog.importSources)) {
    const existingOwner = importSourceOwnerMap.get(source);
    if (existingOwner !== undefined) {
      throw new Error(
        `Duplicate import source "${source}" in ${loadedCatalog.displayPath}; it is already provided by ${existingOwner}.`,
      );
    }

    importSourceOwnerMap.set(source, loadedCatalog.displayPath);
    importSource[source] = cloneImportSourceConfig(config);
  }

  for (const category of loadedCatalog.catalog.categoryOrder) {
    if (!categoryOrder.includes(category)) {
      categoryOrder.push(category);
    }
  }

  for (const [title, definition] of Object.entries(loadedCatalog.catalog.snippets)) {
    const existingOwner = snippetOwnerMap.get(title);
    if (existingOwner !== undefined) {
      throw new Error(
        `Duplicate snippet key "${title}" in ${loadedCatalog.displayPath}; it is already provided by ${existingOwner}.`,
      );
    }

    snippetOwnerMap.set(title, loadedCatalog.displayPath);

    const snippet: Info_Snippet = {
      id: `${loadedCatalog.idPrefix}:${title}`,
      title,
      category: definition.category,
      label: definition.label,
      prefix: definition.prefix,
      body: normalizeSnippetBody(definition.body),
      description: definition.description,
      imports: normalizeImports(definition.imports),
      insertionMode: definition.insertionMode,
    };

    snippetByCategory[snippet.category] ??= [];
    snippetByCategory[snippet.category].push(snippet);
    snippetById[snippet.id] = snippet;
  }
}

export function createEmptySnippetRepository(): Info_SnippetRepository {
  return {
    categoryOrder: [],
    snippetByCategory: {},
    snippetById: {},
    importSource: {},
  };
}

export function buildSnippetRepository(
  loadedCatalogList: readonly Info_LoadedSnippetCatalog[],
  favoriteFile: DictSnippetFavoriteFile,
): Info_SnippetRepositoryBuildResult {
  const snippetByCategory: Record<string, Info_Snippet[]> = {};
  const snippetById: Record<string, Info_Snippet> = {};
  const importSource: Record<string, DictImportSourceConfig> = {};
  const catalogCategoryOrder: string[] = [];
  const snippetOwnerMap = new Map<string, string>();
  const importSourceOwnerMap = new Map<string, string>();
  const warningList: string[] = [];

  for (const loadedCatalog of loadedCatalogList) {
    addCatalogToRepository(
      loadedCatalog,
      snippetByCategory,
      snippetById,
      importSource,
      catalogCategoryOrder,
      snippetOwnerMap,
      importSourceOwnerMap,
    );
  }

  const knownImportSourceSet = new Set(Object.keys(importSource));
  for (const snippet of Object.values(snippetById)) {
    addWarningForUnknownImportSources(snippet, knownImportSourceSet, warningList);
  }

  for (const [title, definition] of Object.entries(favoriteFile.snippets)) {
    const snippet: Info_Snippet = {
      id: `favorite:${title}`,
      title,
      category: STR_FAVORITE_CATEGORY,
      label: definition.label ?? title,
      prefix: definition.prefix,
      body: normalizeSnippetBody(definition.body),
      description:
        definition.description ?? "No description is available for this snippet.",
      imports: normalizeImports(definition.imports),
      insertionMode: definition.insertionMode ?? "line",
    };

    addWarningForUnknownImportSources(snippet, knownImportSourceSet, warningList);

    snippetByCategory[snippet.category] ??= [];
    snippetByCategory[snippet.category].push(snippet);
    snippetById[snippet.id] = snippet;
  }

  const categoryOrder: string[] = [];
  if ((snippetByCategory[STR_FAVORITE_CATEGORY]?.length ?? 0) > 0) {
    categoryOrder.push(STR_FAVORITE_CATEGORY);
  }

  for (const category of catalogCategoryOrder) {
    if (
      (snippetByCategory[category]?.length ?? 0) > 0 &&
      !categoryOrder.includes(category)
    ) {
      categoryOrder.push(category);
    }
  }

  const unknownCategoryList = Object.keys(snippetByCategory)
    .filter((category) => !categoryOrder.includes(category))
    .sort(compareNamesCaseInsensitive);
  categoryOrder.push(...unknownCategoryList);

  return {
    repository: {
      categoryOrder,
      snippetByCategory,
      snippetById,
      importSource,
    },
    warnings: warningList,
  };
}

function replaceRecord<T>(
  targetRecord: Record<string, T>,
  sourceRecord: Record<string, T>,
): void {
  for (const key of Object.keys(targetRecord)) {
    delete targetRecord[key];
  }

  Object.assign(targetRecord, sourceRecord);
}

export function replaceSnippetRepository(
  repository: Info_SnippetRepository,
  nextRepository: Info_SnippetRepository,
): void {
  repository.categoryOrder.splice(
    0,
    repository.categoryOrder.length,
    ...nextRepository.categoryOrder,
  );
  replaceRecord(repository.snippetByCategory, nextRepository.snippetByCategory);
  replaceRecord(repository.snippetById, nextRepository.snippetById);
  replaceRecord(repository.importSource, nextRepository.importSource);
}
