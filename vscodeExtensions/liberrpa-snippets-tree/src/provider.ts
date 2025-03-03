// FileName: Provider.ts
import * as vscode from "vscode";
import { getSnippets } from "./handleSnippets";
import { DictSnippetNodeInfo } from "./interface";
import { dictIconMapping } from "./utils";

class Node {
  /*
  The Node object to store information from Snippets, as a middle layer between Snippets dictionary and vscode TreeView.
  There are 2 kinds of Node: category node and snippet node.
  "label" is used to as the title of tree item, it will be category's name or snippet's name.
  "description" and "body" to make up tooltip of tree item if it is a snippet node.
  "childrenNode" to store snippet nodes if it is a category node.
  */
  constructor(
    public readonly label: string,
    public readonly description?: string,
    public readonly body?: string[],
    public readonly childrenNode?: Node[]
  ) {}
}

const DROPMARKER =
  "$LIBERRPA_SNIPPET_DROP_PLACEHOLDER(you may see it when you undo(Ctrl+Z), please undo again.)";
let snippetToDrop: vscode.SnippetString | null = null;

export class SnippetTreeDataProvider
  implements vscode.TreeDataProvider<Node>, vscode.TreeDragAndDropController<Node>
{
  // The snippetsTreeView will only have 2 layer: "Category" layer and "Snippet" layer.

  /*  handleDrop will only work in TreeView, not in editor, so drop plain text and then insert snippet by other logic.  */
  readonly dragMimeTypes: readonly string[] = ["text/plain"];
  readonly dropMimeTypes: readonly string[] = ["text/plain"];

  // Give it a default value to express the loading state.
  private snippetsDict: {
    [key: string]: {
      [key: string]: DictSnippetNodeInfo;
    };
  } = { Loading: {} };

  constructor() {
    this.initSnippetsDict();
  }

  initSnippetsDict() {
    try {
      // Give it a default value.
      this.snippetsDict = getSnippets();
    } catch (e) {
      console.error("Error when initializing snippets dictionary:", e);
    }
  }

  getChildren(nodeObj: Node | undefined): vscode.ProviderResult<Node[]> {
    // The first function that must be implemented, vscode will call it automatically to create the tree.

    // console.log("--getChildren--");
    if (nodeObj) {
      // When click a node, vscode will call it to try to get its children(if it has).
      return Promise.resolve(
        this.getChildrenNode(nodeObj.label, nodeObj.childrenNode)
      );
    } else {
      // When open the TreeView, it's undefined, vscode will call it to get all category node.
      return Promise.resolve(this.getCategoryNode());
    }
  }

  getTreeItem(nodeObj: Node): vscode.TreeItem {
    // The seconds function that must be implemented. The function will be invoked automatically to generate vscode TreeItem when a node is visible.
    // console.log("--getTreeItem--");
    if (this.isSnippetNode(nodeObj)) {
      // The snippets.
      return {
        label: nodeObj.label,
        tooltip:
          nodeObj.body?.join("\n") + "\n----------------\n" + nodeObj.description,
        collapsibleState: vscode.TreeItemCollapsibleState.None,
        command: {
          command: "LiberRPA.insertSnippet",
          title: "Insert Snippet",
          // arguments's type is any[], even nodeObj.body is an array, it becomes a string in command if use it as the arguments directly, so add a square brackets to nest it.
          arguments: [nodeObj.body],
        },
      };
    } else {
      // The category.
      // Use related icon for different category.
      return {
        label: nodeObj.label,
        tooltip: "Click to expand",
        collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
        iconPath: new vscode.ThemeIcon(dictIconMapping[nodeObj.label] ?? "library"),
      };
    }
  }

  private getChildrenNode(
    _label: string,
    childrenNodeArr: Node[] | undefined
  ): Node[] {
    // console.log("--getChildrenNode--");
    if (!childrenNodeArr) {
      // It is a snippets node.
      return [];
    }

    // It is a category node.
    return childrenNodeArr;
  }

  private getCategoryNode(): Node[] {
    // The functon getTreeItem will be invoked by getChildren(), to generate the category nodes.
    // console.log("--getCategoryNode--");
    const arrCategoryNode = Object.keys(this.snippetsDict).map(
      (strCategoryName) => {
        // console.log("strCategoryName:", strCategoryName);

        const arrChildrenNode: Node[] = Object.keys(
          this.snippetsDict[strCategoryName]
        ).map((strSnippetName) => {
          return new Node(
            strSnippetName,
            this.snippetsDict[strCategoryName][strSnippetName].description,
            this.snippetsDict[strCategoryName][strSnippetName].body,
            undefined
          );
        });

        return new Node(strCategoryName, undefined, undefined, arrChildrenNode);
      }
    );

    return arrCategoryNode;
  }

  private isSnippetNode(nodeData: any): boolean {
    // console.log("--isSnippetNode--");
    return nodeData.body /*  && nodeData.description */;
  }

  handleDrag(
    sourceNode: readonly Node[],
    dataTransfer: vscode.DataTransfer,
    _token: vscode.CancellationToken
  ): Thenable<void> | void {
    // console.log("--handleDrag--");

    if (sourceNode.length === 1 && this.isSnippetNode(sourceNode[0])) {
      const nodeObj = sourceNode[0];
      const strSnippet = nodeObj.body?.join("\n") || "";
      snippetToDrop = new vscode.SnippetString(strSnippet);

      dataTransfer.set("text/plain", new vscode.DataTransferItem(DROPMARKER));
    }
  }
}

export function onTextChange(event: vscode.TextDocumentChangeEvent): void {
  // console.log("--onTextChange--");

  if (snippetToDrop) {
    const changes = event.contentChanges;
    // console.log(changes);

    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showInformationMessage("No active editor!");
      return;
    }

    // Will only have one change object due to DROPMARKER is an one-line string..
    const change = changes[0];
    const positionStart = change.range.start;
    const positionEnd = positionStart.translate(0, change.text.length);

    // Save snippetToDrop to a variable, otherwise the .then() will use a null value.
    const snippetTemp = snippetToDrop;

    editor
      .edit((editBuilder) => {
        editBuilder.delete(new vscode.Range(positionStart, positionEnd));
      })
      .then(() => {
        editor.insertSnippet(snippetTemp, positionStart);
      });
  }

  // Anyway, reset the variable, I think it is more robust.
  snippetToDrop = null;
}
