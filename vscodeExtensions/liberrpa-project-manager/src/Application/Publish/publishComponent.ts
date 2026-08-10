// FileName: publishComponent.ts

import * as vscode from "vscode";

import { log } from "../../Adapter/VsCode/output";
import { getErrorMessage } from "../../Common/utils";
import {
  ComponentManagementOperationError,
  publishComponent as runPublishComponent,
} from "../../Adapter/Python/componentManagementClient";
import {
  getWorkspaceProjectType,
  updateProjectTypeContext,
} from "../../Adapter/VsCode/projectTypeContext";
import type { DictProtocolResult_Publish } from "../../Domain/ComponentManagement/componentManagementTypes";
import { logComponentManagementWarnings } from "../componentManagementOutput";

let boolPublishBusy = false;

function getSingleWorkspaceFolder(): vscode.WorkspaceFolder {
  const arrWorkspaceFolder = vscode.workspace.workspaceFolders;
  if (arrWorkspaceFolder === undefined || arrWorkspaceFolder.length !== 1) {
    throw new Error("Publish Component requires exactly one open workspace folder.");
  }
  return arrWorkspaceFolder[0];
}

function resolveProjectRelativeFile(
  workspaceFolder: vscode.WorkspaceFolder,
  relativePath: string,
): vscode.Uri {
  if (relativePath.includes("\\")) {
    throw new Error(`Component Management returned a non-portable path: ${relativePath}`);
  }

  const arrPathPart = relativePath.split("/");
  if (
    arrPathPart.length === 0 ||
    arrPathPart.some((pathPart) => pathPart === "" || pathPart === "." || pathPart === "..")
  ) {
    throw new Error(
      `Component Management returned an invalid relative path: ${relativePath}`,
    );
  }

  return vscode.Uri.joinPath(workspaceFolder.uri, ...arrPathPart);
}

async function openPreparationFiles(
  workspaceFolder: vscode.WorkspaceFolder,
  result: DictProtocolResult_Publish,
): Promise<void> {
  const astSnippetsDocument = await vscode.workspace.openTextDocument(
    resolveProjectRelativeFile(workspaceFolder, result.astSnippetsFile),
  );
  await vscode.window.showTextDocument(astSnippetsDocument, {
    viewColumn: vscode.ViewColumn.Active,
    preview: false,
    preserveFocus: true,
  });

  const snippetsConfigDocument = await vscode.workspace.openTextDocument(
    resolveProjectRelativeFile(workspaceFolder, result.snippetsJsoncFile),
  );
  await vscode.window.showTextDocument(snippetsConfigDocument, {
    viewColumn: vscode.ViewColumn.Active,
    preview: false,
    preserveFocus: false,
  });
}

function getPublishSummary(result: DictProtocolResult_Publish): string {
  if (result.status === "preparationCreated") {
    return (
      "Component publish preparation was created. " +
      `Generated: ${String(result.generatedCount)}, ` +
      `skipped: ${String(result.skippedCount)}, ` +
      `warnings: ${String(result.warningCount)}.`
    );
  }

  const strStatus =
    result.status === "published"
      ? `Component ${result.packageName} ${result.version} was published.`
      : `Component ${result.packageName} ${result.version} was already ` +
        "published with identical content.";

  return (
    `${strStatus} Generated: ${String(result.generatedCount)}, ` +
    `excluded: ${String(result.excludedCount)}, ` +
    `hand-written: ${String(result.handWrittenCount)}, ` +
    `final: ${String(result.finalCount)}, ` +
    `skipped: ${String(result.skippedCount)}, ` +
    `warnings: ${String(result.warningCount)}.`
  );
}

export async function publishCurrentComponent(): Promise<void> {
  if (boolPublishBusy) {
    void vscode.window.showInformationMessage(
      "Another Publish Component operation is already running.",
    );
    return;
  }

  boolPublishBusy = true;
  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Publishing Component...",
        cancellable: false,
      },
      async () => {
        const workspaceFolder = getSingleWorkspaceFolder();
        if ((await getWorkspaceProjectType(workspaceFolder)) !== "component") {
          await updateProjectTypeContext();
          throw new Error("Publish Component is only available for a Component Project.");
        }

        if (!(await vscode.workspace.saveAll())) {
          throw new Error("Could not save all files before publishing the Component.");
        }

        const operationResult = await runPublishComponent(workspaceFolder.uri.fsPath);
        logComponentManagementWarnings(operationResult.warnings);

        if (operationResult.result.status === "preparationCreated") {
          await openPreparationFiles(workspaceFolder, operationResult.result);
        } else {
          log.info(
            `Published Component Wheel: ${operationResult.result.wheelFileName}\n` +
              `Component Wheel SHA-256: ${operationResult.result.sha256}`,
          );
        }

        const strSummary = getPublishSummary(operationResult.result);
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
    log.error(`Publish Component failed: ${strMessage}`);
    void vscode.window.showErrorMessage(`Publish Component failed: ${strMessage}`);
  } finally {
    boolPublishBusy = false;
  }
}
