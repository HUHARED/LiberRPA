// FileName: treeViewProvider.ts
import { log } from "./output";
import type { DictSnippetNodeCommandArg, DictSnippetRepository } from "./interface";
import type { TreeNode } from "./nodeDefinition";
import { CategoryNode, SnippetNode } from "./nodeDefinition";
import { dictIconMapping } from "./utils";
import { updateManagedImports } from "./managedImports";

import * as vscode from "vscode";

const STR_DROP_MARKER =
  "$LIBERRPA_SNIPPET_DROP_PLACEHOLDER(you may see it when you undo(Ctrl+Z), please undo again.)";

export class SnippetTreeDataProvider
  implements vscode.TreeDataProvider<TreeNode>, vscode.TreeDragAndDropController<TreeNode>
{
  // VS Code inserts this plain-text marker into the editor during a drag.
  // checkWhetherHandleDrop() replaces it with the real snippet.
  readonly dragMimeTypes: readonly string[] = ["text/plain"];

  // This tree does not accept drops from other sources.
  readonly dropMimeTypes: readonly string[] = [];

  private readonly categoryNodes: CategoryNode[];
  private snippetToDrop: DictSnippetNodeCommandArg | null = null;

  constructor(private readonly repository: DictSnippetRepository) {
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
            dictSnippet.insertionMode
          )
      );

      return new CategoryNode(
        `category:${strCategoryName}`,
        strCategoryName,
        arrSnippetNodes
      );
    });
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
        vscode.TreeItemCollapsibleState.None
      );

      treenodeItem.id = nodeObj.id;
      treenodeItem.tooltip = `${nodeObj.body.join("\n")}\n----------------\n${nodeObj.description}`;

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
      vscode.TreeItemCollapsibleState.Collapsed
    );
    treenodeItem.id = nodeObj.id;
    treenodeItem.tooltip = "Click to expand";
    treenodeItem.iconPath = new vscode.ThemeIcon(
      dictIconMapping[nodeObj.label] ?? "library"
    );
    return treenodeItem;
  }

  handleDrag(
    sourceNodes: readonly TreeNode[],
    dataTransfer: vscode.DataTransfer,
    _token: vscode.CancellationToken
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

    this.snippetToDrop = {
      title: nodeObj.title,
      body: nodeObj.body,
      imports: nodeObj.imports,
      insertionMode: nodeObj.insertionMode,
    };

    // Drop a marker first. checkWhetherHandleDrop() will replace it with the real snippet.
    log.debug(`[Drag] Started dragging snippet: ${nodeObj.title}.`);
    dataTransfer.set("text/plain", new vscode.DataTransferItem(STR_DROP_MARKER));
  }

  public async handlePossibleSnippetDrop(
    event: vscode.TextDocumentChangeEvent
  ): Promise<void> {
    if (!this.snippetToDrop) {
      // Don't add log here. It will be triggered always.
      return;
    }

    // Ignore unrelated document changes while a snippet is being dragged.
    // Only the change containing DROP_MARKER belongs to the drop operation.
    const markerChange = event.contentChanges.find((change) =>
      change.text.includes(STR_DROP_MARKER)
    );
    if (markerChange !== undefined) {
      log.trace("markerChange=", String(markerChange?.text));
    }
    if (!markerChange) {
      return;
    }

    const editor = vscode.window.visibleTextEditors.find(
      (visibleEditor) =>
        visibleEditor.document.uri.toString() === event.document.uri.toString()
    );
    if (!editor) {
      this.snippetToDrop = null;
      throw new Error(`No visible editor was found for ${event.document.uri.fsPath}.`);
    }

    const intMarkerIndex = markerChange.text.indexOf(STR_DROP_MARKER);
    const intMarkerStartOffset = markerChange.rangeOffset + intMarkerIndex;
    const intMarkerEndOffset = intMarkerStartOffset + STR_DROP_MARKER.length;
    const positionMarkerStart = event.document.positionAt(intMarkerStartOffset);
    const positionMarkerEnd = event.document.positionAt(intMarkerEndOffset);

    // Save the current drop metadata locally and clear the shared state first.
    // Deleting the marker and inserting the snippet trigger more document-change events, which must not be handled as another drag operation.
    const droppedSnippet = this.snippetToDrop;
    this.snippetToDrop = null;

    const boolDeleted = await editor.edit((editBuilder) => {
      editBuilder.delete(new vscode.Range(positionMarkerStart, positionMarkerEnd));
    });
    if (!boolDeleted) {
      throw new Error(
        `Failed to delete the drop marker for snippet: ${droppedSnippet.title}.`
      );
    }

    const boolInserted = await editor.insertSnippet(
      new vscode.SnippetString(droppedSnippet.body.join("\n")),
      positionMarkerStart
    );
    if (!boolInserted) {
      throw new Error(`Failed to insert dragged snippet: ${droppedSnippet.title}.`);
    }

    await updateManagedImports(
      editor,
      this.repository.importSources,
      droppedSnippet.imports
    );

    log.debug(`[Drop] Inserted snippet: ${droppedSnippet.title}.`);
  }
}
