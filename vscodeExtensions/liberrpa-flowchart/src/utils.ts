// FileName: utils.ts
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import type { WebviewToExtensionMessage } from "./interface";
import { isExecuteMode, parseFlowProjectFromText } from "./checkFlowchart";

export const outputChannel = vscode.window.createOutputChannel("liberrpa-flowchart");
outputChannel.show(true);

export function isWebviewMessage(value: unknown): value is WebviewToExtensionMessage {
  if (!value || typeof value !== "object") {
    return false;
  }

  const msg = value as Record<string, unknown>;

  if (msg.command === "ready") {
    return true;
  }

  if (msg.command === "update") {
    return typeof msg.data === "string";
  }

  if (msg.command === "open") {
    return typeof msg.path === "string";
  }

  if (msg.command === "execute" || msg.command === "executeProject") {
    const data = msg.data as Record<string, unknown> | undefined;

    if (!data || typeof data !== "object") {
      return false;
    }

    if (msg.command === "execute") {
      return typeof data.pyFile === "string" && isExecuteMode(data.executeMode);
    }

    return isExecuteMode(data.executeMode);
  }

  return false;
}

export function getCustomArgNames(document: vscode.TextDocument): string[] {
  // outputChannel.appendLine("--getCustomArgNames--");

  // Find the related workspace.
  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);

  if (!workspaceFolder) {
    return [];
  }

  const projectFlowPath = path.join(workspaceFolder.uri.fsPath, "project.flow");

  // Try to get the open "project.flow" document
  const openDocument = vscode.workspace.textDocuments.find(
    (doc) => doc.uri.fsPath === projectFlowPath
  );

  let content: string | undefined;

  if (openDocument) {
    // Read the latest unsaved content from the open document
    content = openDocument.getText();
    // outputChannel.appendLine("Using unsaved project.flow content.");
  } else {
    // Fallback: read from disk if the file is not open in the editor

    if (!fs.existsSync(projectFlowPath)) {
      // outputChannel.appendLine("Not found project.flow.");
      return [];
    }

    try {
      content = fs.readFileSync(projectFlowPath, "utf-8");
      // outputChannel.appendLine("Using saved project.flow content from disk.");
    } catch (e) {
      outputChannel.appendLine(
        `Error reading project.flow: ${e instanceof Error ? e.message : String(e)}}`
      );
      return [];
    }
  }

  // Parse JSON and extract customPrjArgs
  try {
    const dictProject = parseFlowProjectFromText(content);
    return dictProject.customPrjArgs.map((item) => item[0]);
  } catch (e) {
    outputChannel.appendLine(
      `Parsing project.flow JSON failed: ${e instanceof Error ? e.message : String(e)}}`
    );
  }

  return [];
}

export function resolveWorkspacePythonFile(
  workspaceFolder: vscode.WorkspaceFolder,
  pyFile: string
): vscode.Uri {
  const strInput = pyFile.trim();

  if (!strInput) {
    throw new Error("Python file path cannot be empty.");
  }

  if (strInput.includes("\0")) {
    throw new Error("Python file path contains an invalid null character.");
  }

  if (strInput.includes("\\")) {
    throw new Error(`Use "/" as the folder separator: ${pyFile}`);
  }

  if (path.isAbsolute(strInput)) {
    throw new Error(`Python file path must be relative to the workspace: ${pyFile}`);
  }

  let strRelativePath = strInput;

  if (strRelativePath.startsWith("./")) {
    strRelativePath = strRelativePath.slice(2);
  }

  if (!strRelativePath.toLowerCase().endsWith(".py")) {
    throw new Error(`Python file path must end with .py: ${pyFile}`);
  }

  const arrPathParts = strRelativePath.split("/");

  if (arrPathParts.some((part) => part === "" || part === "." || part === "..")) {
    throw new Error(`Python file path contains invalid path segment: ${pyFile}`);
  }

  for (const part of arrPathParts) {
    const strNameWithoutExt =
      part === arrPathParts[arrPathParts.length - 1] ? path.parse(part).name : part;

    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(strNameWithoutExt)) {
      throw new Error(
        `Invalid Python module name "${strNameWithoutExt}" in path: ${pyFile}`
      );
    }
  }

  const strWorkspaceRoot = path.resolve(workspaceFolder.uri.fsPath);
  const strTargetPath = path.resolve(strWorkspaceRoot, strRelativePath);

  const strWorkspaceRootLower = strWorkspaceRoot.toLowerCase();
  const strTargetPathLower = strTargetPath.toLowerCase();

  if (
    strTargetPathLower !== strWorkspaceRootLower &&
    !strTargetPathLower.startsWith(strWorkspaceRootLower + path.sep)
  ) {
    throw new Error(`Python file path escapes the workspace: ${pyFile}`);
  }

  return vscode.Uri.file(strTargetPath);
}
