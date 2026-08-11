// FileName: snippetTreeDataProvider.ts

import * as vscode from "vscode";

import { log } from "./output";
import { DICT_CATEGORY_ICON } from "./snippetTreeIcons";
import type { DictSnippetNodeCommandArg } from "../../Domain/Snippet/snippetTypes";
import type { TreeNode } from "../../Domain/Snippet/snippetNodes";
import { CategoryNode, SnippetNode } from "../../Domain/Snippet/snippetNodes";
import type { Info_SnippetRepository } from "../../Domain/Snippet/snippetTypes";

export const STR_SNIPPET_DRAG_MIME = "application/vnd.code.tree.liberrpa.snippetstreeview";

export class SnippetTreeDataProvider
  implements
    vscode.TreeDataProvider<TreeNode>,
    vscode.TreeDragAndDropController<TreeNode>,
    vscode.Disposable
{
  private readonly treeDataChangeEmitter = new vscode.EventEmitter<TreeNode | undefined>();

  readonly onDidChangeTreeData = this.treeDataChangeEmitter.event;

  readonly dragMimeTypes: readonly string[] = [STR_SNIPPET_DRAG_MIME];

  // This tree does not accept drops from other sources.
  readonly dropMimeTypes: readonly string[] = [];

  private categoryNodeList: CategoryNode[] = [];
  private draggedSnippetNode: SnippetNode | undefined;
  private dragCancellationListener: vscode.Disposable | undefined;

  constructor(repository: Info_SnippetRepository) {
    this.refresh(repository);
  }

  refresh(repository: Info_SnippetRepository): void {
    this.finishDrag();

    this.categoryNodeList = repository.categoryOrder.map((categoryName) => {
      const snippetNodeList = (repository.snippetByCategory[categoryName] ?? []).map(
        (snippet) => new SnippetNode(snippet),
      );

      return new CategoryNode(`category:${categoryName}`, categoryName, snippetNodeList);
    });

    this.treeDataChangeEmitter.fire(undefined);
  }

  getChildren(node: TreeNode | undefined): vscode.ProviderResult<TreeNode[]> {
    // Root call: return categories. Category call: return snippets. Snippet call: no children.
    if (node === undefined) {
      return this.categoryNodeList;
    }
    return node.kind === "category" ? node.children : [];
  }

  getTreeItem(node: TreeNode): vscode.TreeItem {
    /* Convert an internal tree node into a VS Code TreeItem. */

    if (node.kind === "snippet") {
      const snippet = node.snippet;
      const treeItem = new vscode.TreeItem(
        snippet.label,
        vscode.TreeItemCollapsibleState.None,
      );
      treeItem.id = snippet.id;

      // Clicking a snippet node runs the internal insert command.
      const commandArg: DictSnippetNodeCommandArg = {
        title: snippet.title,
        body: snippet.body,
        imports: snippet.imports,
        insertionMode: snippet.insertionMode,
      };
      treeItem.command = {
        command: "LiberRPA.insertSnippetByNodeClicking",
        // Required by VS Code. This internal command is not contributed to Command Palette.
        title: "Insert Snippet By Node Clicking",
        // Pass one command argument object. VS Code command arguments must be provided as an array.
        arguments: [commandArg],
      };

      return treeItem;
    }

    // Category.
    const treeItem = new vscode.TreeItem(
      node.label,
      vscode.TreeItemCollapsibleState.Collapsed,
    );
    treeItem.id = node.id;
    treeItem.tooltip = "Click to expand";
    treeItem.iconPath = new vscode.ThemeIcon(DICT_CATEGORY_ICON[node.label] ?? "library");
    return treeItem;
  }

  resolveTreeItem(treeItem: vscode.TreeItem, node: TreeNode): vscode.TreeItem {
    // vscode seems to have a bug that a node's tooltip sometimes appears while draging it quickly. Use the function and finishDrag() to handle this issue.
    if (node.kind === "snippet") {
      const snippet = node.snippet;
      treeItem.tooltip =
        node === this.draggedSnippetNode
          ? ""
          : `${snippet.body.join("\n")}\n----------------\n${snippet.description}`;
    }
    return treeItem;
  }

  finishDrag(): void {
    const draggedSnippetNode = this.draggedSnippetNode;
    if (draggedSnippetNode === undefined) {
      return;
    }

    this.draggedSnippetNode = undefined;
    this.dragCancellationListener?.dispose();
    this.dragCancellationListener = undefined;

    // A tooltip request made during the drag resolved to an empty string. Refresh the item so its complete preview can be resolved on the next hover.
    this.treeDataChangeEmitter.fire(draggedSnippetNode);
  }

  handleDrag(
    sourceNodeList: readonly TreeNode[],
    dataTransfer: vscode.DataTransfer,
    token: vscode.CancellationToken,
  ): Thenable<void> | void {
    if (sourceNodeList.length !== 1) {
      // Allow drag one node at once.
      return;
    }

    const node = sourceNodeList[0];
    if (node.kind !== "snippet") {
      // Cannot drag category nodes.
      return;
    }

    this.finishDrag();
    this.draggedSnippetNode = node;
    this.dragCancellationListener = token.onCancellationRequested(() => {
      this.finishDrag();
    });

    log.debug(`[Drag] Started dragging snippet: ${node.snippet.title}.`);
    dataTransfer.set(STR_SNIPPET_DRAG_MIME, new vscode.DataTransferItem(node.snippet.id));
  }

  dispose(): void {
    this.finishDrag();
    this.treeDataChangeEmitter.dispose();
  }
}
