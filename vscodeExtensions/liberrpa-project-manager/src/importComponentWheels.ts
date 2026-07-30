// FileName: importComponentWheels.ts

import * as vscode from "vscode";

import { log } from "./output";
import {
  ComponentManagementOperationError,
  importComponentWheels as runImportComponentWheels,
} from "./componentManagement/operations";
import { getErrorMessage } from "./utils";

let boolImportComponentWheelsBusy = false;

export async function importComponentWheels(): Promise<boolean> {
  if (boolImportComponentWheelsBusy) {
    void vscode.window.showInformationMessage(
      "Another Import Component Wheels operation is already running.",
    );
    return false;
  }

  const arrWheelUri = await vscode.window.showOpenDialog({
    title: "Import Component Wheels into ComponentRepository",
    openLabel: "Import Component Wheels",
    canSelectFiles: true,
    canSelectFolders: false,
    canSelectMany: true,
    filters: {
      "Python Wheel": ["whl"],
    },
  });
  if (arrWheelUri === undefined || arrWheelUri.length === 0) {
    return false;
  }

  boolImportComponentWheelsBusy = true;

  try {
    return await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Importing Component Wheels...",
        cancellable: false,
      },
      async () => {
        const operationResult = await runImportComponentWheels(
          arrWheelUri.map((wheelUri) => wheelUri.fsPath),
        );

        for (const warning of operationResult.warnings) {
          log.warn(warning.message);
          if (warning.details !== undefined) {
            log.debug(JSON.stringify(warning.details, null, 2));
          }
        }

        for (const component of operationResult.result.components) {
          log.info(
            `${component.status === "imported" ? "Imported" : "Already imported"}: ` +
              `${component.packageName} ${component.version} (${component.componentId}), ` +
              `SHA-256 ${component.sha256}.`,
          );
        }

        const strSummary =
          "Component Wheel import completed. " +
          `Imported: ${String(operationResult.result.importedCount)}, ` +
          `already imported: ${String(operationResult.result.alreadyImportedCount)}, ` +
          `warnings: ${String(operationResult.warnings.length)}.`;
        log.info(strSummary);

        if (operationResult.warnings.length > 0) {
          void vscode.window.showWarningMessage(
            `${strSummary} See the Output panel for details.`,
          );
        } else {
          void vscode.window.showInformationMessage(strSummary);
        }

        return true;
      },
    );
  } catch (e: unknown) {
    if (e instanceof ComponentManagementOperationError) {
      log.error(`Import Component Wheels failed [${e.code}]: ${e.message}`);
      if (Object.keys(e.details).length > 0) {
        log.debug(JSON.stringify(e.details, null, 2));
      }
      void vscode.window.showErrorMessage(`Import Component Wheels failed: ${e.message}`);
      return false;
    }

    const strErrorMessage = getErrorMessage(e);
    log.error(`Import Component Wheels failed: ${strErrorMessage}`);
    void vscode.window.showErrorMessage(
      `Import Component Wheels failed: ${strErrorMessage}`,
    );
    return false;
  } finally {
    boolImportComponentWheelsBusy = false;
  }
}
