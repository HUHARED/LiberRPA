// FileName: extension.ts
import * as vscode from "vscode";

import { outputChannel } from "./commonValue";
import { createProject } from "./createFolder";

export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('"liberrpa-project-manager" is now active.');

  const disposable = vscode.commands.registerCommand(
    "LiberRPA.createProject",
    createProject
  );

  context.subscriptions.push(disposable);
}

export function deactivate() {
  outputChannel.appendLine('"liberrpa-project-manager" is now deactivated.');
}
