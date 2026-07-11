// FileName: interface.ts

export type SnippetInsertionMode = "line" | "cursor";

// source name, modules needed in the source.
export type DictImportsInfo = Record<string, string[]>;

export interface ImportSourceConfig {
  // the config about import source, has only order now.
  order: string[];
}

export interface DictSnippetDefinition {
  category?: string;
  label?: string;

  prefix: string;
  body: string[] | string;

  description?: string;
  imports?: DictImportsInfo;

  /**
   * line:
   *   Insert on the current empty line, or create a new line first.
   *
   * cursor:
   *   Insert directly at the current cursor or replace the current selection.
   */
  insertionMode?: SnippetInsertionMode;
}

export interface DictSnippetCatalogFile {
  schemaVersion: 1;

  // For Snippet TreeView
  categoryOrder: string[];

  // Source name, module order in the source
  importSources: Record<string, ImportSourceConfig>;
  snippets: Record<string, DictSnippetDefinition>;
}

export interface DictSnippetFavoriteFile {
  schemaVersion: 1;
  snippets: Record<string, DictSnippetDefinition>;
}

export interface DictSnippetTotalInfo {
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

export interface DictSnippetRepository {
  // handleSnippets.ts creates a repository.
  // Providers use the repository to create snippet items and completion items.
  categoryOrder: string[];
  categories: Record<string, DictSnippetTotalInfo[]>;
  importSources: Record<string, ImportSourceConfig>;
}

export interface DictSnippetNodeCommandArg {
  // title is used for logging; imports contains the data used by import management.
  title: string;
  body: string[];
  imports: DictImportsInfo;
  insertionMode: SnippetInsertionMode;
}

export interface DictSnippetCompletionCommandArg {
  // title is used for logging; imports contains the data used by import management.
  title: string;
  imports: DictImportsInfo;
}
