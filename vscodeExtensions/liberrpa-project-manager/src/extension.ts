// FileName: extension.ts
import * as vscode from "vscode";

import { log } from "./output";
import { packageProject } from "./packageFolder";
import { ProjectManagerPanel } from "./projectManagerPanel";
import { registerProjectTypeContext } from "./projectTypeContext";
import { publishComponent } from "./publishComponent";

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);
  log.info('"liberrpa-project-manager" is now active.');

  registerProjectTypeContext(context);

  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.createProject", () => {
      ProjectManagerPanel.show(context, "createProject");
    }),
  );

  // TODO: Modify Project Packaging later.
  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.packageProject", packageProject),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.publishComponent", publishComponent),
  );
}

export function deactivate(): void {
  log.info('"liberrpa-project-manager" is now deactivated.');
}
