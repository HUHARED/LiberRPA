// FileName: projectTypeContext.ts
import * as vscode from "vscode";

import { log } from "./output";
import { getErrorMessage } from "./utils";

export type ProjectTypeContext = "component" | "flow" | "none" | "invalid";

const STR_PROJECT_TYPE_CONTEXT_KEY = "liberrpaProjectManager.projectType";

async function isFile(uri: vscode.Uri): Promise<boolean> {
  try {
    const stat = await vscode.workspace.fs.stat(uri);
    return (stat.type & vscode.FileType.File) !== 0;
  } catch {
    return false;
  }
}

export async function getWorkspaceProjectType(
  workspaceFolder: vscode.WorkspaceFolder,
): Promise<ProjectTypeContext> {
  const componentManifestUri = vscode.Uri.joinPath(workspaceFolder.uri, "component.json");
  const flowManifestUri = vscode.Uri.joinPath(workspaceFolder.uri, "flow.json");

  const [componentManifestExists, flowManifestExists] = await Promise.all([
    isFile(componentManifestUri),
    isFile(flowManifestUri),
  ]);

  if (componentManifestExists && flowManifestExists) {
    return "invalid";
  }

  if (componentManifestExists) {
    return "component";
  }

  if (flowManifestExists) {
    return "flow";
  }

  return "none";
}

export async function updateProjectTypeContext(): Promise<void> {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  let projectType: ProjectTypeContext = "none";

  if (workspaceFolders !== undefined && workspaceFolders.length === 1) {
    projectType = await getWorkspaceProjectType(workspaceFolders[0]);
  }

  await vscode.commands.executeCommand(
    "setContext",
    STR_PROJECT_TYPE_CONTEXT_KEY,
    projectType,
  );
}

export function registerProjectTypeContext(context: vscode.ExtensionContext): void {
  const componentManifestWatcher =
    vscode.workspace.createFileSystemWatcher("**/component.json");
  const flowManifestWatcher = vscode.workspace.createFileSystemWatcher("**/flow.json");

  const refreshContext = (): void => {
    void updateProjectTypeContext().catch((e: unknown) => {
      log.error(`Failed to update Project type context: ${getErrorMessage(e)}`);
    });
  };

  componentManifestWatcher.onDidCreate(refreshContext);
  componentManifestWatcher.onDidChange(refreshContext);
  componentManifestWatcher.onDidDelete(refreshContext);

  flowManifestWatcher.onDidCreate(refreshContext);
  flowManifestWatcher.onDidChange(refreshContext);
  flowManifestWatcher.onDidDelete(refreshContext);

  context.subscriptions.push(
    componentManifestWatcher,
    flowManifestWatcher,
    vscode.workspace.onDidChangeWorkspaceFolders(refreshContext),
  );

  refreshContext();
}
