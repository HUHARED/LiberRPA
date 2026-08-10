// FileName: publishComponent.ts

import * as vscode from "vscode";

import {
  publishComponent as runPublishComponent,
  type Info_ComponentManagement_OperationResult,
} from "../../Adapter/Python/componentManagementClient";
import {
  getWorkspaceProjectType,
  updateProjectTypeContext,
} from "../../Adapter/VsCode/projectTypeContext";
import type { Str_PublishComponentFile } from "../../Adapter/Webview/projectManagerMessages";
import type { DictProtocolResult_Publish } from "../../Domain/ComponentManagement/componentManagementTypes";
import { readComponentManifest } from "../../Domain/Project/projectManifest";
import type { DictProjectManifest_Component } from "../../Domain/Project/projectTypes";

const STR_AST_SNIPPETS_FILE = "_Snippets/ast.snippets.json";
const STR_SNIPPETS_CONFIG_FILE = "_Snippets/snippets.jsonc";

interface Info_PublishComponentData {
  projectPath: string;
  manifest: DictProjectManifest_Component;

  astSnippetsFile: string;
  snippetsJsoncFile: string;
  astSnippetsFileExists: boolean;
  snippetsJsoncFileExists: boolean;
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

async function isRegularFile(fileUri: vscode.Uri): Promise<boolean> {
  try {
    const fileStat = await vscode.workspace.fs.stat(fileUri);
    return (
      (fileStat.type & vscode.FileType.File) !== 0 &&
      (fileStat.type & vscode.FileType.SymbolicLink) === 0
    );
  } catch {
    return false;
  }
}

async function ensureComponentProject(
  workspaceFolder: vscode.WorkspaceFolder,
): Promise<void> {
  if ((await getWorkspaceProjectType(workspaceFolder)) === "component") {
    return;
  }

  await updateProjectTypeContext();
  throw new Error("Publish Component is only available for a Component Project.");
}

export async function loadPublishComponentData(
  workspaceFolder: vscode.WorkspaceFolder,
  publishResult: DictProtocolResult_Publish | null = null,
): Promise<Info_PublishComponentData> {
  await ensureComponentProject(workspaceFolder);

  const manifestFileUri = vscode.Uri.joinPath(workspaceFolder.uri, "component.json");
  const astSnippetsFile = publishResult?.astSnippetsFile ?? STR_AST_SNIPPETS_FILE;
  const snippetsJsoncFile = publishResult?.snippetsJsoncFile ?? STR_SNIPPETS_CONFIG_FILE;
  const astSnippetsFileUri = resolveProjectRelativeFile(workspaceFolder, astSnippetsFile);
  const snippetsJsoncFileUri = resolveProjectRelativeFile(
    workspaceFolder,
    snippetsJsoncFile,
  );

  const [astSnippetsFileExists, snippetsJsoncFileExists] = await Promise.all([
    isRegularFile(astSnippetsFileUri),
    isRegularFile(snippetsJsoncFileUri),
  ]);

  return {
    projectPath: workspaceFolder.uri.fsPath,
    manifest: readComponentManifest(manifestFileUri.fsPath),
    astSnippetsFile,
    snippetsJsoncFile,
    astSnippetsFileExists,
    snippetsJsoncFileExists,
  };
}

export async function publishComponentProject(
  workspaceFolder: vscode.WorkspaceFolder,
): Promise<Info_ComponentManagement_OperationResult<DictProtocolResult_Publish>> {
  await ensureComponentProject(workspaceFolder);
  return await runPublishComponent(workspaceFolder.uri.fsPath);
}

export async function openPublishComponentFile(
  workspaceFolder: vscode.WorkspaceFolder,
  file: Str_PublishComponentFile,
  publishResult: DictProtocolResult_Publish | null,
): Promise<void> {
  await ensureComponentProject(workspaceFolder);

  const relativePath =
    file === "astSnippets"
      ? (publishResult?.astSnippetsFile ?? STR_AST_SNIPPETS_FILE)
      : (publishResult?.snippetsJsoncFile ?? STR_SNIPPETS_CONFIG_FILE);
  const fileUri = resolveProjectRelativeFile(workspaceFolder, relativePath);

  if (!(await isRegularFile(fileUri))) {
    throw new Error(`The Component publish file does not exist: ${relativePath}`);
  }

  const document = await vscode.workspace.openTextDocument(fileUri);
  await vscode.window.showTextDocument(document, {
    viewColumn: vscode.ViewColumn.Active,
    preview: false,
    preserveFocus: false,
  });
}
