// FileName: extension.ts
import * as vscode from "vscode";
import { SnippetTreeDataProvider, onTextChange } from "./provider";
import { insertSnippet } from "./utils";
import { outputChannel } from "./output";


export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('"liberrpa-snippets-tree" is now active.');

  const provider = new SnippetTreeDataProvider();
  context.subscriptions.push(
    vscode.window.createTreeView("LiberRPA.snippetsTreeView", {
      treeDataProvider: provider,
      showCollapseAll: true,
      canSelectMany: false,
      dragAndDropController: provider,
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.insertSnippet", (body: string[]) => {
      insertSnippet(body);
    })
  );

  vscode.workspace.onDidChangeTextDocument(onTextChange);
}
export function deactivate() {
  outputChannel.appendLine('"liberrpa-snippets-tree" is now deactivated.');
}
