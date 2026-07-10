// FileName: treeViewProvider.ts
import { log } from "./output";
import type { SnippetNodeCommandArg, SnippetTotalInfo } from "./interface";
import type { TreeNode } from "./nodeDefinition";
import { CategoryNode, SnippetNode } from "./nodeDefinition";
import { dictIconMapping } from "./utils";
import { getSnippets, getImportManifest } from "./handleSnippets";
import { updateManagedImports } from "./managedImports";

import * as vscode from "vscode";

const DROP_MARKER =
  "$LIBERRPA_SNIPPET_DROP_PLACEHOLDER(you may see it when you undo(Ctrl+Z), please undo again.)";

let snippetToDrop: SnippetNodeCommandArg | null = null;

export class SnippetTreeDataProvider
  implements vscode.TreeDataProvider<TreeNode>, vscode.TreeDragAndDropController<TreeNode>
{
  // The snippets tree has two levels: category nodes and snippet nodes.

  // Dragging a tree item into the editor only needs text/plain.
  // The editor receives a temporary marker, then checkWhetherHandleDrop() replaces it with the real snippet.
  readonly dragMimeTypes: readonly string[] = ["text/plain"];

  // This tree does not accept drops from other sources.
  readonly dropMimeTypes: readonly string[] = [];

  private snippetsDict: Record<string, Record<string, SnippetTotalInfo>> = {};

  constructor() {
    this.initSnippetsDict();
  }

  private initSnippetsDict(): void {
    try {
      // Load snippets once when the provider is created.
      this.snippetsDict = getSnippets();
    } catch (e) {
      log.error(
        `Error when initializing snippets dictionary:${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }

  private getCategoryNodes(): CategoryNode[] {
    return Object.entries(this.snippetsDict).map(([categoryName, snippets]) => {
      const snippetNodes = Object.entries(snippets).map(([snippetLabel, snippetInfo]) => {
        return new SnippetNode(
          snippetLabel,
          snippetInfo.title,
          snippetInfo.description,
          snippetInfo.body,
          snippetInfo.importNames,
        );
      });

      return new CategoryNode(categoryName, snippetNodes);
    });
  }

  getChildren(nodeObj: TreeNode | undefined): vscode.ProviderResult<TreeNode[]> {
    // Root call: return categories. Category call: return snippets. Snippet call: no children.

    if (!nodeObj) {
      return this.getCategoryNodes();
    }

    if (nodeObj.kind === "category") {
      return nodeObj.children;
    }

    return [];
  }

  getTreeItem(nodeObj: TreeNode): vscode.TreeItem {
    // Convert an internal tree node into a VS Code TreeItem.

    if (nodeObj.kind === "snippet") {
      const commandArg: SnippetNodeCommandArg = {
        title: nodeObj.title,
        body: nodeObj.body,
        importNames: nodeObj.importNames,
      };

      return {
        label: nodeObj.label,
        tooltip: `${nodeObj.body.join("\n")}\n----------------\n${nodeObj.description}`,
        collapsibleState: vscode.TreeItemCollapsibleState.None,
        // Clicking a snippet node runs the internal insert command.
        command: {
          command: "LiberRPA.insertSnippetByNodeClicking",
          // Required by VS Code. This internal command is not contributed to Command Palette.
          title: "Insert Snippet By Node Clicking",
          // Pass one command argument object. VS Code command arguments must be provided as an array.
          arguments: [commandArg],
        },
      };
    }

    return {
      label: nodeObj.label,
      tooltip: "Click to expand",
      collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
      // Use a category-specific icon when available.
      iconPath: new vscode.ThemeIcon(dictIconMapping[nodeObj.label] ?? "library"),
    };
  }

  handleDrag(
    sourceNodes: readonly TreeNode[],
    dataTransfer: vscode.DataTransfer,
    _token: vscode.CancellationToken,
  ): Thenable<void> | void {
    if (sourceNodes.length !== 1) {
      return;
    }

    const nodeObj = sourceNodes[0];
    if (nodeObj.kind !== "snippet") {
      return;
    }

    snippetToDrop = {
      title: nodeObj.title,
      body: nodeObj.body,
      importNames: nodeObj.importNames,
    };

    log.debug(
      `[Drag] Start dragging snippet: ${snippetToDrop.title}, imports=[${snippetToDrop.importNames.join(", ")}].`,
    );

    // Drop a marker first. checkWhetherHandleDrop() will replace it with the real snippet.
    dataTransfer.set("text/plain", new vscode.DataTransferItem(DROP_MARKER));
  }
}

async function handleSnippetDropTextChange(
  event: vscode.TextDocumentChangeEvent,
): Promise<void> {
  if (!snippetToDrop) {
    // Don't add log here. It will be triggered always.
    return;
  }

  // Ignore unrelated document changes while a snippet is being dragged.
  // Only the change containing DROP_MARKER belongs to the drop operation.
  const markerChange = event.contentChanges.find((change) =>
    change.text.includes(DROP_MARKER),
  );

  if (markerChange !== undefined) {
    log.trace("markerChange=", String(markerChange?.text));
  }

  if (!markerChange) {
    return;
  }

  const editor = vscode.window.visibleTextEditors.find(
    (visibleEditor) =>
      visibleEditor.document.uri.toString() === event.document.uri.toString(),
  );

  if (!editor) {
    log.error(
      `[Drop] No visible editor was found for document: ${event.document.uri.fsPath}.`,
    );
    snippetToDrop = null;
    return;
  }

  const markerIndex = markerChange.text.indexOf(DROP_MARKER);

  const markerStartOffset = markerChange.rangeOffset + markerIndex;
  const markerEndOffset = markerStartOffset + DROP_MARKER.length;

  const markerStart = event.document.positionAt(markerStartOffset);
  const markerEnd = event.document.positionAt(markerEndOffset);

  // Save the current drop metadata locally and clear the shared state immediately.
  // Deleting the marker and inserting the snippet will trigger additional
  // text-change events, which must not be processed as another drop.
  const droppedSnippet = snippetToDrop;
  snippetToDrop = null;

  log.debug(
    `[Drop] Inserting snippet: ${droppedSnippet.title}, imports=[${droppedSnippet.importNames.join(", ")}].`,
  );

  const deleted = await editor.edit((editBuilder) => {
    editBuilder.delete(new vscode.Range(markerStart, markerEnd));
  });

  if (!deleted) {
    throw new Error(
      `Failed to delete the drop marker for snippet: ${droppedSnippet.title}.`,
    );
  }

  const inserted = await editor.insertSnippet(
    new vscode.SnippetString(droppedSnippet.body.join("\n")),
    markerStart,
  );

  if (!inserted) {
    throw new Error(`Failed to insert dragged snippet: ${droppedSnippet.title}.`);
  }

  await updateManagedImports(editor, getImportManifest(), droppedSnippet.importNames);

  log.debug(`[Drop] Snippet inserted: ${droppedSnippet.title}.`);
}

export async function checkWhetherHandleDrop(
  event: vscode.TextDocumentChangeEvent,
): Promise<void> {
  try {
    await handleSnippetDropTextChange(event);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    log.error(`[Drop] Failed to handle dragged snippet: ${message}`);
    void vscode.window.showErrorMessage(
      `Failed to insert dragged LiberRPA snippet: ${message}`,
    );
    snippetToDrop = null;
  }
}
