// FileName: extension.ts

import * as vscode from "vscode";

import { log } from "./Adapter/VsCode/output";
import { registerProjectTypeContext } from "./Adapter/VsCode/projectTypeContext";
import { ProjectManagerPanel } from "./Adapter/VsCode/projectManagerPanel";
import { publishCurrentComponent } from "./Application/Publish/publishComponent";
import { selectAndImportComponentWheels } from "./Application/Repository/importComponentWheels";
import { rebuildComponentRepositoryIndex } from "./Application/Repository/rebuildRepositoryIndex";

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);
  log.info('"liberrpa-project-manager" is now active.');

  registerProjectTypeContext(context);

  context.subscriptions.push(
    vscode.commands.registerCommand("LiberRPA.createProject", () => {
      ProjectManagerPanel.show(context, "createProject");
    }),
    vscode.commands.registerCommand("LiberRPA.publishComponent", publishCurrentComponent),
    vscode.commands.registerCommand("LiberRPA.manageComponents", () => {
      ProjectManagerPanel.show(context, "manageComponents");
    }),
    vscode.commands.registerCommand(
      "LiberRPA.importComponentWheels",
      selectAndImportComponentWheels,
    ),
    vscode.commands.registerCommand(
      "LiberRPA.rebuildComponentRepositoryIndex",
      rebuildComponentRepositoryIndex,
    ),
  );
}

export function deactivate(): void {
  log.info('"liberrpa-project-manager" is now deactivated.');
}
