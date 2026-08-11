// FileName: snippetTypes.ts

export type SnippetInsertionMode = "line" | "cursor";

// Import source name mapped to the required imported names.
export type DictImportsInfo = Record<string, string[]>;

export interface DictImportSourceConfig {
  // The config about import source.
  order: string[];
  // Component sources use deterministic PackageName_ModuleName aliases.
  aliasMode?: "source_module";
}

export interface DictSnippetDefinition {
  category?: string;
  label?: string;

  prefix: string;
  body: string[] | string;

  description?: string;
  imports?: DictImportsInfo;

  insertionMode?: SnippetInsertionMode;
}

/**
 * The generated catalog has already been normalized by CombineSnippets.py,
 * so these fields are intentionally stricter than user-maintained favorites.
 */
export interface DictCatalogSnippetDefinition {
  category: string;
  label: string;

  prefix: string;
  body: string[];

  description: string;
  imports?: DictImportsInfo;

  insertionMode: SnippetInsertionMode;
}

export interface DictSnippetCatalogFile {
  schemaVersion: 1;

  // For Snippet TreeView
  categoryOrder: string[];

  // Source name, module order in the source
  importSources: Record<string, DictImportSourceConfig>;
  snippets: Record<string, DictCatalogSnippetDefinition>;
}

export interface DictSnippetFavoriteFile {
  schemaVersion: 1;
  snippets: Record<string, DictSnippetDefinition>;
}

export interface Info_LoadedSnippetCatalog {
  idPrefix: string;
  displayPath: string;
  catalog: DictSnippetCatalogFile;
}

export interface Info_Snippet {
  id: string;
  title: string;

  category: string;
  label: string;
  prefix: string;
  body: string[];

  description: string;
  imports: DictImportsInfo;
  insertionMode: SnippetInsertionMode;
}

export interface Info_SnippetRepository {
  categoryOrder: string[];
  snippetByCategory: Record<string, Info_Snippet[]>;
  snippetById: Record<string, Info_Snippet>;
  importSource: Record<string, DictImportSourceConfig>;
}

export interface Info_SnippetRepositoryBuildResult {
  repository: Info_SnippetRepository;
  warnings: string[];
}

export interface DictSnippetNodeCommandArg {
  // title is used for logging; imports contains the data used by import management.
  title: string;
  body: string[];
  imports: DictImportsInfo;
  insertionMode: SnippetInsertionMode;
}
