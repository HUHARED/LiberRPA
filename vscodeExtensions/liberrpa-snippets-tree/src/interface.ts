// FileName: interface.ts

export interface SnippetsItem {
  prefix: string;
  body: string[] | string;
  description?: string;
}

export interface ImportManifest {
  importSource: string;
  importOrder: string[];
  items: Record<string, string[]>;
}

export interface SnippetTotalInfo {
  title: string;
  prefix: string;
  body: string[];
  description: string;
  importNames: string[];
}

export interface SnippetCompletionCommandArg {
  // title works for log, importNames has real effect.
  title: string;
  importNames: string[];
}

export interface SnippetNodeCommandArg {
  title: string;
  body: string[];
  importNames: string[];
}
