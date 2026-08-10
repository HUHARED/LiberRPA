// FileName: importComponentWheels.ts

import * as vscode from "vscode";

import {
  type Info_ComponentManagement_OperationResult,
  ComponentManagementOperationError,
  importComponentWheels as runImportComponentWheels,
} from "../../Adapter/Python/componentManagementClient";
import { log } from "../../Adapter/VsCode/output";
import { getErrorMessage } from "../../Common/utils";
import type {
  DictProtocolResult_ComponentWheelsImported,
} from "../../Domain/ComponentManagement/componentManagementTypes";
import { logComponentManagementWarnings } from "../componentManagementOutput";

let boolImportBusy = false;

export async function selectComponentWheelFilePaths(): Promise<
  string[] | undefined
> {
  const arrWheelUri = await vscode.window.showOpenDialog({
    title: "Import Component Wheels into ComponentRepository",
    openLabel: "Import Component Wheels",
    canSelectFiles: true,
    canSelectFolders: false,
    canSelectMany: true,
    filters: { "Python Wheel": ["whl"] },
  });
  if (arrWheelUri === undefined || arrWheelUri.length === 0) {
    return undefined;
  }

  return arrWheelUri.map((wheelUri) => wheelUri.fsPath);
}

export async function importComponentWheelFiles(
  wheelFilePaths: string[],
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ComponentWheelsImported>
> {
  const operationResult = await runImportComponentWheels(wheelFilePaths);
  logComponentManagementWarnings(operationResult.warnings);

  for (const component of operationResult.result.components) {
    log.info(
      `${component.status === "imported" ? "Imported" : "Already imported"}: ` +
        `${component.packageName} ${component.version} ` +
        `(${component.componentId}), SHA-256 ${component.sha256}.`,
    );
  }

  return operationResult;
}

function getImportSummary(
  operationResult: Info_ComponentManagement_OperationResult<
    DictProtocolResult_ComponentWheelsImported
  >,
): string {
  return (
    "Component Wheel import completed. " +
    `Imported: ${String(operationResult.result.importedCount)}, ` +
    `already imported: ${String(
      operationResult.result.alreadyImportedCount,
    )}, warnings: ${String(operationResult.warnings.length)}.`
  );
}

export async function selectAndImportComponentWheels(): Promise<void> {
  if (boolImportBusy) {
    void vscode.window.showInformationMessage(
      "Another Import Component Wheels operation is already running.",
    );
    return;
  }

  const arrWheelFilePath = await selectComponentWheelFilePaths();
  if (arrWheelFilePath === undefined) {
    return;
  }

  boolImportBusy = true;
  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Importing Component Wheels...",
        cancellable: false,
      },
      async () => {
        const operationResult = await importComponentWheelFiles(arrWheelFilePath);
        const strSummary = getImportSummary(operationResult);
        log.info(strSummary);

        if (operationResult.warnings.length > 0) {
          void vscode.window.showWarningMessage(
            `${strSummary} See the Output panel for details.`,
          );
        } else {
          void vscode.window.showInformationMessage(strSummary);
        }
      },
    );
  } catch (e: unknown) {
    const strMessage = getErrorMessage(e);
    if (e instanceof ComponentManagementOperationError) {
      log.debug(JSON.stringify(e.details, null, 2));
    }
    log.error(`Import Component Wheels failed: ${strMessage}`);
    void vscode.window.showErrorMessage(
      `Import Component Wheels failed: ${strMessage}`,
    );
  } finally {
    boolImportBusy = false;
  }
}
