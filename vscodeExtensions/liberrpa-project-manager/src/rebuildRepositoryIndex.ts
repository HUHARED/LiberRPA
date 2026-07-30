// FileName: rebuildRepositoryIndex.ts
import * as vscode from "vscode";

import { log } from "./output";
import { getErrorMessage } from "./utils";
import type { DictComponentManagementWarning } from "./componentManagement/protocol";
import { runComponentManagement } from "./componentManagement/process";
import { parseRepositoryIndexRebuiltResult } from "./componentManagement/repositoryResult";

let boolRebuildRepositoryIndexBusy = false;

function getWarningMessage(warning: DictComponentManagementWarning): string {
  return warning.message;
}

export async function rebuildRepositoryIndex(): Promise<void> {
  if (boolRebuildRepositoryIndexBusy) {
    void vscode.window.showInformationMessage(
      "Another Rebuild Component Repository Index operation is already running.",
    );
    return;
  }

  boolRebuildRepositoryIndexBusy = true;

  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Rebuilding Component Repository index...",
        cancellable: false,
      },
      async () => {
        const response = await runComponentManagement({
          schemaVersion: 1,
          operation: "rebuildRepositoryIndex",
        });

        if (!response.ok) {
          log.error(
            `Rebuild Component Repository Index failed ` +
              `[${response.error.code}]: ${response.error.message}`,
          );

          if (Object.keys(response.error.details).length > 0) {
            log.debug(
              "Rebuild Component Repository Index error details:\n" +
                JSON.stringify(response.error.details, null, 2),
            );
          }

          void vscode.window.showErrorMessage(
            `Rebuild Component Repository Index failed: ` + response.error.message,
          );
          return;
        }

        const dictResult = parseRepositoryIndexRebuiltResult(response.result);

        for (const warning of response.warnings) {
          log.warn(getWarningMessage(warning));
        }

        const strSummary =
          "Component Repository index was rebuilt. " +
          `Components: ${String(dictResult.componentCount)}, ` +
          `versions: ${String(dictResult.versionCount)}, ` +
          `warnings: ${String(response.warnings.length)}.`;

        log.info(strSummary);

        if (response.warnings.length > 0) {
          void vscode.window.showWarningMessage(
            `${strSummary} See the Output panel for details.`,
          );
        } else {
          void vscode.window.showInformationMessage(strSummary);
        }
      },
    );
  } catch (e: unknown) {
    const strErrorMessage = getErrorMessage(e);

    log.error(`Rebuild Component Repository Index failed: ${strErrorMessage}`);

    void vscode.window.showErrorMessage(
      `Rebuild Component Repository Index failed: ${strErrorMessage}`,
    );
  } finally {
    boolRebuildRepositoryIndexBusy = false;
  }
}
