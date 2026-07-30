// FileName: publishComponent.ts
import * as vscode from "vscode";

import { log } from "./output";
import { getErrorMessage } from "./utils";
import type {
  DictComponentManagementWarning,
  DictProtocolResult_Publish,
} from "./componentManagement/protocol";
import { runComponentManagement } from "./componentManagement/process";
import { parsePublishComponentResult } from "./componentManagement/publishResult";
import { getWorkspaceProjectType, updateProjectTypeContext } from "./projectTypeContext";

let boolPublishBusy = false;

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
  const astSnippetsUri = resolveProjectRelativeFile(
    workspaceFolder,
    result.astSnippetsFile,
  );
  const snippetsJsoncUri = resolveProjectRelativeFile(
    workspaceFolder,
    result.snippetsJsoncFile,
  );

  const astSnippetsDocument = await vscode.workspace.openTextDocument(astSnippetsUri);
  await vscode.window.showTextDocument(astSnippetsDocument, {
    viewColumn: vscode.ViewColumn.Active,
    preview: false,
    preserveFocus: true,
  });

  const snippetsConfigDocument = await vscode.workspace.openTextDocument(snippetsJsoncUri);
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

function getWarningMessage(warning: DictComponentManagementWarning): string {
  if (typeof warning.message === "string" && warning.message.length > 0) {
    return warning.message;
  }

  return JSON.stringify(warning);
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

        const dictResponse = await runComponentManagement({
          schemaVersion: 1,
          operation: "publishComponent",
          projectPath: workspaceFolder.uri.fsPath,
        });

        if (!dictResponse.ok) {
          log.error(
            `Publish Component failed [${dictResponse.error.code}]: ${dictResponse.error.message}`,
          );

          if (Object.keys(dictResponse.error.details).length > 0) {
            log.debug(
              `Publish Component error details:\n${JSON.stringify(dictResponse.error.details, null, 2)}`,
            );
          }

          void vscode.window.showErrorMessage(
            `Publish Component failed: ${dictResponse.error.message}`,
          );
          return;
        }

        const dictResult = parsePublishComponentResult(dictResponse.result);

        for (const warning of dictResponse.warnings) {
          log.warn(getWarningMessage(warning));
        }

        if (dictResult.status === "preparationCreated") {
          await openPreparationFiles(workspaceFolder, dictResult);
        }

        let strSummary: string;

        if (dictResult.status === "published" || dictResult.status === "alreadyPublished") {
          log.info(`Published Component Wheel: ${dictResult.wheelFile}`);
          log.info(`Component Wheel SHA-256: ${dictResult.sha256}`);

          const strPublishStatus =
            dictResult.status === "published"
              ? `Component ${dictResult.packageName} ${dictResult.version} was published.`
              : `Component ${dictResult.packageName} ${dictResult.version} was already published with identical content.`;

          strSummary =
            `${strPublishStatus} ` +
            `Generated: ${String(dictResult.generatedCount)}, ` +
            `excluded: ${String(dictResult.excludedCount)}, ` +
            `hand-written: ${String(dictResult.handWrittenCount)}, ` +
            `final: ${String(dictResult.finalCount)}, ` +
            `skipped: ${String(dictResult.skippedCount)}, ` +
            `warnings: ${String(dictResult.warningCount)}.`;
        } else {
          strSummary =
            "Component publish preparation was created. " +
            `Generated: ${String(dictResult.generatedCount)}, ` +
            `skipped: ${String(dictResult.skippedCount)}, ` +
            `warnings: ${String(dictResult.warningCount)}.`;
        }

        log.info(strSummary);

        if (dictResult.warningCount > 0) {
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
