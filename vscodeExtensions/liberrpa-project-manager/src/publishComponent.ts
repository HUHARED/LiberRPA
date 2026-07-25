// FileName: publishComponent.ts
import * as vscode from "vscode";

import { log } from "./output";
import { getErrorMessage } from "./utils";
import type { ComponentManagementWarning } from "./componentManagementProcess";
import { runComponentManagement } from "./componentManagementProcess";
import { getWorkspaceProjectType, updateProjectTypeContext } from "./projectTypeContext";

interface PublishComponentResultBase {
  componentId: string;
  packageName: string;
  astSnippetsFile: string;
  snippetsConfigFile: string;
  generatedCount: number;
  skippedCount: number;
  warningCount: number;
}

interface PublishPreparationResult extends PublishComponentResultBase {
  status: "preparationCreated" | "preparationUpdated";
}

interface PublishedComponentResult extends PublishComponentResultBase {
  status: "published" | "alreadyPublished";
  version: string;
  wheelFile: string;
  sha256: string;
  excludedCount: number;
  handWrittenCount: number;
  finalCount: number;
}

type PublishComponentResult = PublishPreparationResult | PublishedComponentResult;

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

function getRequiredSha256(value: Record<string, unknown>, key: string): string {
  const fieldValue = getRequiredString(value, key);
  if (!/^[0-9a-f]{64}$/.test(fieldValue)) {
    throw new Error(
      `Component Management result field ${key} must be a lowercase SHA-256 value.`,
    );
  }

  return fieldValue;
}

function parsePublishComponentResult(
  result: Record<string, unknown>,
): PublishComponentResult {
  const status = result.status;
  if (
    status !== "preparationCreated" &&
    status !== "preparationUpdated" &&
    status !== "published" &&
    status !== "alreadyPublished"
  ) {
    throw new Error(`Unsupported Publish Component result status: ${String(status)}.`);
  }

  const baseResult: PublishComponentResultBase = {
    componentId: getRequiredString(result, "componentId"),
    packageName: getRequiredString(result, "packageName"),
    astSnippetsFile: getRequiredString(result, "astSnippetsFile"),
    snippetsConfigFile: getRequiredString(result, "snippetsConfigFile"),
    generatedCount: getRequiredNonNegativeInteger(result, "generatedCount"),
    skippedCount: getRequiredNonNegativeInteger(result, "skippedCount"),
    warningCount: getRequiredNonNegativeInteger(result, "warningCount"),
  };

  if (status === "published" || status === "alreadyPublished") {
    return {
      ...baseResult,
      status,
      version: getRequiredString(result, "version"),
      wheelFile: getRequiredString(result, "wheelFile"),
      sha256: getRequiredSha256(result, "sha256"),
      excludedCount: getRequiredNonNegativeInteger(result, "excludedCount"),
      handWrittenCount: getRequiredNonNegativeInteger(result, "handWrittenCount"),
      finalCount: getRequiredNonNegativeInteger(result, "finalCount"),
    };
  }

  return {
    ...baseResult,
    status,
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
    arrPathParts.some(
      (pathPart) => pathPart === "" || pathPart === "." || pathPart === "..",
    )
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
  result: PublishComponentResult,
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
  const arrWorkspaceFolder = vscode.workspace.workspaceFolders;
  if (arrWorkspaceFolder === undefined || arrWorkspaceFolder.length !== 1) {
    throw new Error("Publish Component requires exactly one open workspace folder.");
  }

  return arrWorkspaceFolder[0];
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
        title: "Publishing Component...",
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

        const result = parsePublishComponentResult(response.result);

        for (const warning of response.warnings) {
          log.warn(getWarningMessage(warning));
        }

        await openPreparationFiles(workspaceFolder, result);

        let strSummary: string;

        if (result.status === "published" || result.status === "alreadyPublished") {
          log.info(`Published Component Wheel: ${result.wheelFile}`);
          log.info(`Component Wheel SHA-256: ${result.sha256}`);

          const strPublishStatus =
            result.status === "published"
              ? `Component ${result.packageName} ${result.version} was published.`
              : `Component ${result.packageName} ${result.version} was already published with identical content.`;

          strSummary =
            `${strPublishStatus} ` +
            `Generated: ${String(result.generatedCount)}, ` +
            `excluded: ${String(result.excludedCount)}, ` +
            `hand-written: ${String(result.handWrittenCount)}, ` +
            `final: ${String(result.finalCount)}, ` +
            `skipped: ${String(result.skippedCount)}, ` +
            `warnings: ${String(result.warningCount)}.`;
        } else {
          const strStatusText =
            result.status === "preparationCreated"
              ? "Component publish preparation was created."
              : "Component publish preparation was updated.";
          strSummary =
            `${strStatusText} Generated: ${String(result.generatedCount)}, ` +
            `skipped: ${String(result.skippedCount)}, ` +
            `warnings: ${String(result.warningCount)}.`;
        }

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
