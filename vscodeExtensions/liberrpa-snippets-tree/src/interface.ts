// FileName: interface.ts

export interface DictSnippetsItem {
  prefix: string;
  body: string[];
  description?: string;
}

export interface DictSnippetNodeInfo {
  body: string[];
  description: string;
}
