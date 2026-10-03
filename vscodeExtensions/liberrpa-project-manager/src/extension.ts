// FileName: extension.ts

import * as vscode from "vscode";

import { log } from "./Adapter/VsCode/output";
import { registerProjectTypeContext } from "./Adapter/VsCode/projectTypeContext";
import { ProjectManagerPanel } from "./Adapter/VsCode/projectManagerPanel";
import { selectAndImportComponentWheels } from "./Application/Repository/importComponentWheels";
import { rebuildComponentRepositoryIndex } from "./Application/Repository/rebuildRepositoryIndex";
import { ConsoleAccount } from "./Application/Console/consoleAccount";
import { ConsoleContextBridge } from "./Adapter/Console/consoleContextBridge";
import { isRecord } from "./Common/typeCheck";

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);
  log.info('"liberrpa-project-manager" is now active.');

  registerProjectTypeContext(context);
  const consoleAccount = new ConsoleAccount(context);
  context.subscriptions.push(consoleAccount);
  const consoleContextBridge = new ConsoleContextBridge(() =>
    consoleAccount.getPythonCredential(),
  );
  context.subscriptions.push(consoleContextBridge);
  const environmentVariableCollection = context.environmentVariableCollection;
  environmentVariableCollection.persistent = false;
  environmentVariableCollection.description =
    "Connect Python to this Editor's Console account.";
  context.subscriptions.push({ dispose: () => environmentVariableCollection.clear() });

  function updatePythonEnvironment(): void {
    for (const [strName, strValue] of Object.entries(
      consoleContextBridge.getEnvironment(),
    )) {
      // Empty values override inherited credentials from another Editor or Executor.
      environmentVariableCollection.replace(strName, strValue ?? "");
    }
  }

  context.subscriptions.push(consoleAccount.onDidChangeState(updatePythonEnvironment));
  updatePythonEnvironment();
  const promiseBridgeInitialization = consoleContextBridge.initialization.catch(() => {
    log.error("The local Console credential pipe could not be started.");
  });
  const promisePythonContextInitialization = Promise.all([
    promiseBridgeInitialization,
    consoleAccount.waitForLocalCredential(),
  ]);
  context.subscriptions.push(
    vscode.debug.registerDebugConfigurationProvider("debugpy", {
      async resolveDebugConfigurationWithSubstitutedVariables(_folder, configuration) {
        await promisePythonContextInitialization;
        const environmentValue: unknown = configuration.env;
        if (environmentValue !== undefined && !isRecord(environmentValue)) {
          throw new Error("The Python debug environment must be an object.");
        }
        const dictPythonEnvironment: Record<string, unknown> = { ...environmentValue };
        for (const [strName, strValue] of Object.entries(
          consoleContextBridge.getEnvironment(),
        )) {
          for (const strKey of Object.keys(dictPythonEnvironment)) {
            if (strKey.toLowerCase() === strName.toLowerCase()) {
              delete dictPythonEnvironment[strKey];
            }
          }
          dictPythonEnvironment[strName] = strValue ?? null;
        }
        configuration.env = dictPythonEnvironment;
        return configuration;
      },
    }),
  );

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

  await promisePythonContextInitialization;
  updatePythonEnvironment();
}

export function deactivate(): void {
  log.info('"liberrpa-project-manager" is now deactivated.');
}
