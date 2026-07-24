// FileName: treeViewProvider.ts
import { log } from "./output";
import type { DictSnippetNodeCommandArg, DictSnippetRepository } from "./interface";
import type { TreeNode } from "./nodeDefinition";
import { CategoryNode, SnippetNode } from "./nodeDefinition";
import { dictIconMapping } from "./utils";

import * as vscode from "vscode";

export const STR_SNIPPET_DRAG_MIME = "application/vnd.code.tree.liberrpa.snippetstreeview";

export class SnippetTreeDataProvider
  implements vscode.TreeDataProvider<TreeNode>, vscode.TreeDragAndDropController<TreeNode>
{
  private readonly treeDataChangeEmitter = new vscode.EventEmitter<TreeNode | undefined>();

  readonly onDidChangeTreeData = this.treeDataChangeEmitter.event;

  readonly dragMimeTypes: readonly string[] = [STR_SNIPPET_DRAG_MIME];

  // This tree does not accept drops from other sources.
  readonly dropMimeTypes: readonly string[] = [];

  private categoryNodes: CategoryNode[] = [];
  private draggedSnippetNode: SnippetNode | undefined;
  private dragCancellationListener: vscode.Disposable | undefined;

  constructor(repository: DictSnippetRepository) {
    this.refresh(repository);
  }

  refresh(repository: DictSnippetRepository): void {
    this.finishDrag();

    this.categoryNodes = repository.categoryOrder.map((strCategoryName) => {
      const arrSnippetNodes = (repository.categories[strCategoryName] ?? []).map(
        (dictSnippet) =>
          new SnippetNode(
            dictSnippet.id,
            dictSnippet.label,
            dictSnippet.title,
            dictSnippet.description,
            dictSnippet.body,
            dictSnippet.imports,
            dictSnippet.insertionMode,
          ),
      );

      return new CategoryNode(
        `category:${strCategoryName}`,
        strCategoryName,
        arrSnippetNodes,
      );
    });

    this.treeDataChangeEmitter.fire(undefined);
  }

  getChildren(nodeObj: TreeNode | undefined): vscode.ProviderResult<TreeNode[]> {
    // Root call: return categories. Category call: return snippets. Snippet call: no children.
    if (!nodeObj) {
      return this.categoryNodes;
    }

    if (nodeObj.kind === "category") {
      return nodeObj.children;
    }

    return [];
  }

  getTreeItem(nodeObj: TreeNode): vscode.TreeItem {
    /* Convert an internal tree node into a VS Code TreeItem. */

    if (nodeObj.kind === "snippet") {
      const treenodeItem = new vscode.TreeItem(
        nodeObj.label,
        vscode.TreeItemCollapsibleState.None,
      );

      treenodeItem.id = nodeObj.id;

      // Clicking a snippet node runs the internal insert command.
      const dictCommandArg: DictSnippetNodeCommandArg = {
        title: nodeObj.title,
        body: nodeObj.body,
        imports: nodeObj.imports,
        insertionMode: nodeObj.insertionMode,
      };
      treenodeItem.command = {
        command: "LiberRPA.insertSnippetByNodeClicking",
        // Required by VS Code. This internal command is not contributed to Command Palette.
        title: "Insert Snippet By Node Clicking",
        // Pass one command argument object. VS Code command arguments must be provided as an array.
        arguments: [dictCommandArg],
      };

      return treenodeItem;
    }

    // Category.
    const treenodeItem = new vscode.TreeItem(
      nodeObj.label,
      vscode.TreeItemCollapsibleState.Collapsed,
    );
    treenodeItem.id = nodeObj.id;
    treenodeItem.tooltip = "Click to expand";
    treenodeItem.iconPath = new vscode.ThemeIcon(
      dictIconMapping[nodeObj.label] ?? "library",
    );
    return treenodeItem;
  }

  resolveTreeItem(treenodeItem: vscode.TreeItem, nodeObj: TreeNode): vscode.TreeItem {
    // vscode seems to have a bug that a node's tooltip sometimes appears while draging it quickly. Use the function and finishDrag() to handle this issue.
    if (nodeObj.kind === "snippet") {
      treenodeItem.tooltip =
        nodeObj === this.draggedSnippetNode
          ? ""
          : `${nodeObj.body.join("\n")}\n----------------\n${nodeObj.description}`;
    }

    return treenodeItem;
  }

  finishDrag(): void {
    const draggedSnippetNode = this.draggedSnippetNode;
    if (!draggedSnippetNode) {
      return;
    }

    this.draggedSnippetNode = undefined;
    this.dragCancellationListener?.dispose();
    this.dragCancellationListener = undefined;

    // A tooltip request made during the drag resolved to an empty string. Refresh the item so its complete preview can be resolved on the next hover.
    this.treeDataChangeEmitter.fire(draggedSnippetNode);
  }

  handleDrag(
    sourceNodes: readonly TreeNode[],
    dataTransfer: vscode.DataTransfer,
    token: vscode.CancellationToken,
  ): Thenable<void> | void {
    if (sourceNodes.length !== 1) {
      // Allow drag one node at once.
      return;
    }

    const nodeObj = sourceNodes[0];
    if (nodeObj.kind !== "snippet") {
      // Cannot drag category nodes.
      return;
    }

    this.finishDrag();
    this.draggedSnippetNode = nodeObj;
    this.dragCancellationListener = token.onCancellationRequested(() => {
      this.finishDrag();
    });

    log.debug(`[Drag] Started dragging snippet: ${nodeObj.title}.`);
    dataTransfer.set(STR_SNIPPET_DRAG_MIME, new vscode.DataTransferItem(nodeObj.id));
  }
}
