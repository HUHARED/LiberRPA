// FileName: rebuildRepositoryIndex.ts

import * as vscode from "vscode";

import { log } from "../../Adapter/VsCode/output";
import { getErrorMessage } from "../../Common/utils";
import {
  ComponentManagementOperationError,
  rebuildRepositoryIndex as runRebuildRepositoryIndex,
} from "../../Adapter/Python/componentManagementClient";
import { logComponentManagementWarnings } from "../componentManagementOutput";

let boolRebuildBusy = false;

export async function rebuildComponentRepositoryIndex(): Promise<void> {
  if (boolRebuildBusy) {
    void vscode.window.showInformationMessage(
      "Another Rebuild Component Repository Index operation is already running.",
    );
    return;
  }

  boolRebuildBusy = true;
  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Rebuilding Component Repository Index...",
        cancellable: false,
      },
      async () => {
        const operationResult = await runRebuildRepositoryIndex();
        logComponentManagementWarnings(operationResult.warnings);

        const strSummary =
          "Component Repository index was rebuilt. " +
          `Components: ${String(operationResult.result.componentCount)}, ` +
          `versions: ${String(operationResult.result.versionCount)}, ` +
          `warnings: ${String(operationResult.warnings.length)}.`;
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
    const strMessage =
      e instanceof ComponentManagementOperationError ? e.message : getErrorMessage(e);
    if (e instanceof ComponentManagementOperationError) {
      log.debug(JSON.stringify(e.details, null, 2));
    }
    log.error(`Rebuild Component Repository Index failed: ${strMessage}`);
    void vscode.window.showErrorMessage(
      `Rebuild Component Repository Index failed: ${strMessage}`,
    );
  } finally {
    boolRebuildBusy = false;
  }
}
