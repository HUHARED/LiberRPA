// FileName: publishComponent.ts
import * as vscode from "vscode";

import { log } from "./output";
import { getErrorMessage } from "./utils";
import type { ComponentManagementWarning } from "./componentManagementProcess";
import { runComponentManagement } from "./componentManagementProcess";
import { getWorkspaceProjectType, updateProjectTypeContext } from "./projectTypeContext";

interface PublishPreparationResult {
  status: "preparationCreated" | "preparationUpdated";
  componentId: string;
  packageName: string;
  astSnippetsFile: string;
  snippetsConfigFile: string;
  generatedCount: number;
  skippedCount: number;
  warningCount: number;
}

let boolPublishBusy = false;

function getRequiredString(value: Record<string, unknown>, key: string): string {
  const fieldValue = value[key];
  if (typeof fieldValue !== "string" || fieldValue.length === 0) {
    throw new Error(`Component Management result field ${key} must be a non-empty string.`);
  }

  return fieldValue;
}

function getRequiredNonNegativeInteger(
  value: Record<string, unknown>,
  key: string,
): number {
  const fieldValue = value[key];
  if (typeof fieldValue !== "number" || !Number.isInteger(fieldValue) || fieldValue < 0) {
    throw new Error(
      `Component Management result field ${key} must be a non-negative integer.`,
    );
  }

  return fieldValue;
}

function parsePublishPreparationResult(
  result: Record<string, unknown>,
): PublishPreparationResult {
  const status = result.status;
  if (status !== "preparationCreated" && status !== "preparationUpdated") {
    throw new Error(`Unsupported Publish Component result status: ${String(status)}.`);
  }

  return {
    status,
    componentId: getRequiredString(result, "componentId"),
    packageName: getRequiredString(result, "packageName"),
    astSnippetsFile: getRequiredString(result, "astSnippetsFile"),
    snippetsConfigFile: getRequiredString(result, "snippetsConfigFile"),
    generatedCount: getRequiredNonNegativeInteger(result, "generatedCount"),
    skippedCount: getRequiredNonNegativeInteger(result, "skippedCount"),
    warningCount: getRequiredNonNegativeInteger(result, "warningCount"),
  };
}

function resolveProjectRelativeFile(
  workspaceFolder: vscode.WorkspaceFolder,
  relativePath: string,
): vscode.Uri {
  if (relativePath.includes("\\")) {
    throw new Error(`Component Management returned a non-portable path: ${relativePath}`);
  }

  const arrPathParts = relativePath.split("/");
  if (
    arrPathParts.length === 0 ||
    arrPathParts.some((pathPart) => pathPart === "" || pathPart === "." || pathPart === "..")
  ) {
    throw new Error(
      `Component Management returned an invalid relative path: ${relativePath}`,
    );
  }

  return vscode.Uri.joinPath(workspaceFolder.uri, ...arrPathParts);
}

function getWarningMessage(warning: ComponentManagementWarning): string {
  if (typeof warning.message === "string" && warning.message.length > 0) {
    return warning.message;
  }

  return JSON.stringify(warning);
}

async function openPreparationFiles(
  workspaceFolder: vscode.WorkspaceFolder,
  result: PublishPreparationResult,
): Promise<void> {
  const astSnippetsUri = resolveProjectRelativeFile(
    workspaceFolder,
    result.astSnippetsFile,
  );
  const snippetsConfigUri = resolveProjectRelativeFile(
    workspaceFolder,
    result.snippetsConfigFile,
  );

  const astSnippetsDocument = await vscode.workspace.openTextDocument(astSnippetsUri);
  await vscode.window.showTextDocument(astSnippetsDocument, {
    viewColumn: vscode.ViewColumn.Active,
    preview: false,
    preserveFocus: true,
  });

  const snippetsConfigDocument = await vscode.workspace.openTextDocument(snippetsConfigUri);
  await vscode.window.showTextDocument(snippetsConfigDocument, {
    viewColumn: vscode.ViewColumn.Active,
    preview: false,
    preserveFocus: false,
  });
}

function getSingleWorkspaceFolder(): vscode.WorkspaceFolder {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (workspaceFolders === undefined || workspaceFolders.length !== 1) {
    throw new Error("Publish Component requires exactly one open workspace folder.");
  }

  return workspaceFolders[0];
}

export async function publishComponent(): Promise<void> {
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
        title: "Preparing Component publish...",
        cancellable: false,
      },
      async () => {
        const workspaceFolder = getSingleWorkspaceFolder();
        const projectType = await getWorkspaceProjectType(workspaceFolder);

        if (projectType !== "component") {
          await updateProjectTypeContext();
          throw new Error("Publish Component is only available for a Component Project.");
        }

        const boolSaved = await vscode.workspace.saveAll();
        if (!boolSaved) {
          throw new Error("Could not save all files before publishing the Component.");
        }

        const response = await runComponentManagement({
          schemaVersion: 1,
          operation: "publishComponent",
          projectPath: workspaceFolder.uri.fsPath,
        });

        if (!response.ok) {
          log.error(
            `Publish Component failed [${response.error.code}]: ${response.error.message}`,
          );

          if (Object.keys(response.error.details).length > 0) {
            log.debug(
              `Publish Component error details:\n${JSON.stringify(response.error.details, null, 2)}`,
            );
          }

          void vscode.window.showErrorMessage(
            `Publish Component failed: ${response.error.message}`,
          );
          return;
        }

        const result = parsePublishPreparationResult(response.result);

        for (const warning of response.warnings) {
          log.warn(getWarningMessage(warning));
        }

        await openPreparationFiles(workspaceFolder, result);

        const strStatusText =
          result.status === "preparationCreated"
            ? "Component publish preparation was created."
            : "Component publish preparation was updated.";
        const strSummary =
          `${strStatusText} Generated: ${String(result.generatedCount)}, ` +
          `skipped: ${String(result.skippedCount)}, warnings: ${String(result.warningCount)}.`;

        log.info(strSummary);

        if (result.warningCount > 0) {
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
    log.error(`Publish Component failed: ${strErrorMessage}`);
    void vscode.window.showErrorMessage(`Publish Component failed: ${strErrorMessage}`);
  } finally {
    boolPublishBusy = false;
  }
}
