// FileName: extension.ts

import * as vscode from "vscode";

import { log } from "./Adapter/VsCode/output";
import { registerProjectTypeContext } from "./Adapter/VsCode/projectTypeContext";
import { ProjectManagerPanel } from "./Adapter/VsCode/projectManagerPanel";
import { selectAndImportComponentWheels } from "./Application/Repository/importComponentWheels";
import { rebuildComponentRepositoryIndex } from "./Application/Repository/rebuildRepositoryIndex";
import { ConsoleAccount } from "./Application/Console/consoleAccount";

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);
  log.info('"liberrpa-project-manager" is now active.');

  registerProjectTypeContext(context);
  const consoleAccount = new ConsoleAccount(context);
  context.subscriptions.push(consoleAccount);

  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.createProject", () => {
      ProjectManagerPanel.show(context, "createProject", consoleAccount);
    }),
    vscode.commands.registerCommand("LiberRPA.packageProject", () => {
      ProjectManagerPanel.show(context, "packageProject", consoleAccount);
    }),
    vscode.commands.registerCommand("LiberRPA.publishComponent", () => {
      ProjectManagerPanel.show(context, "publishComponent", consoleAccount);
    }),
    vscode.commands.registerCommand("LiberRPA.manageComponents", () => {
      ProjectManagerPanel.show(context, "manageComponents", consoleAccount);
    }),
    vscode.commands.registerCommand(
      "LiberRPA.importComponentWheels",
      selectAndImportComponentWheels,
    ),
    vscode.commands.registerCommand(
      "LiberRPA.rebuildComponentRepositoryIndex",
      rebuildComponentRepositoryIndex,
    ),
    vscode.commands.registerCommand("LiberRPA.console", () => {
      ProjectManagerPanel.show(context, "console", consoleAccount);
    }),
  );
}

export function deactivate(): void {
  log.info('"liberrpa-project-manager" is now deactivated.');
}
