// FileName: extension.ts
import * as vscode from "vscode";

import { outputChannel } from "./commonValue";
import { createProject } from "./createFolder";
import { packageProject } from "./packageFolder";

export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('"liberrpa-project-manager" is now active.');

  const disposable1 = vscode.commands.registerCommand(
    "LiberRPA.createProject",
    createProject
  );

  context.subscriptions.push(disposable1);

  const disposable2 = vscode.commands.registerCommand(
    "LiberRPA.packageProject",
    packageProject
  );

  context.subscriptions.push(disposable2);
}

export function deactivate() {
  outputChannel.appendLine('"liberrpa-project-manager" is now deactivated.');
}
