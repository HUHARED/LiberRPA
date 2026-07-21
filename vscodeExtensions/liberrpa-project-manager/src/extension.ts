// FileName: extension.ts
import * as vscode from "vscode";

import { log } from "./output";
import { packageProject } from "./packageFolder";
import { ProjectManagerPanel } from "./projectManagerPanel";

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);
  log.info('"liberrpa-project-manager" is now active.');

  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.createProject", () => {
      ProjectManagerPanel.show(context, "createProject");
    }),
  );

  // TODO: Modify Project Packaging later.
  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.packageProject", packageProject),
  );
}

export function deactivate(): void {
  log.info('"liberrpa-project-manager" is now deactivated.');
}
