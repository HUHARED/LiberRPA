// FileName: snippetNodes.ts

import type { Info_Snippet } from "./snippetTypes";

export type TreeNode = CategoryNode | SnippetNode;

export class CategoryNode {
  readonly kind = "category";

  constructor(
    public readonly id: string,
    public readonly label: string,
    public readonly iconId: string,
    public readonly children: SnippetNode[],
  ) {}
}

export class SnippetNode {
  readonly kind = "snippet";

  constructor(public readonly snippet: Info_Snippet) {}
}
