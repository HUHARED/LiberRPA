// FileName: nodeDefinition.ts

export type TreeNode = CategoryNode | SnippetNode;

export class CategoryNode {
  readonly kind = "category";

  constructor(
    public readonly label: string,
    public readonly children: SnippetNode[],
  ) {}
}

export class SnippetNode {
  readonly kind = "snippet";

  constructor(
    public readonly label: string,
    public readonly title: string,
    public readonly description: string,
    public readonly body: string[],
    public readonly importNames: string[],
  ) {}
}
