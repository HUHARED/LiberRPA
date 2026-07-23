// FileName: utils.ts
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import type { WebviewToExtensionMessage } from "./interface";
import { isExecuteMode, parseFlowProjectFromText } from "./checkFlowchart";
import { getRiskyPyModuleNameReason } from "./riskyPyModuleNames";

const REGEX_PYTHON_PATH_NAME = /^[A-Za-z_][A-Za-z0-9_]*$/;

const SET_RESERVED_WINDOWS_PATH_NAMES = new Set<string>([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  "COM1",
  "COM2",
  "COM3",
  "COM4",
  "COM5",
  "COM6",
  "COM7",
  "COM8",
  "COM9",
  "LPT1",
  "LPT2",
  "LPT3",
  "LPT4",
  "LPT5",
  "LPT6",
  "LPT7",
  "LPT8",
  "LPT9",
]);

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

export function validatePythonImportSafety(pyFile: string): void {
  const reason = getRiskyPyModuleNameReason(pyFile);

  if (reason) {
    throw new Error(`${reason}\nPath: ${pyFile}`);
  }
}

export function validateProjectBlockPythonFiles(
  workspaceFolder: vscode.WorkspaceFolder,
  document: vscode.TextDocument,
): void {
  const dictProject = parseFlowProjectFromText(document.getText());

  for (const node of dictProject.nodes) {
    if (node.type !== "Block") {
      continue;
    }

    const pyFile = node.properties.pyFile;

    const uriPythonFile = resolveWorkspacePythonFile(workspaceFolder, pyFile);
    validatePythonImportSafety(pyFile);

    if (
      !fs.existsSync(uriPythonFile.fsPath) ||
      !fs.statSync(uriPythonFile.fsPath).isFile()
    ) {
      throw new Error(`Block Python file does not exist: ${uriPythonFile.fsPath}`);
    }
  }
}

export function resolveWorkspacePythonFile(
  workspaceFolder: vscode.WorkspaceFolder,
  pyFile: string,
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

  const intLastPathPartIndex = arrPathParts.length - 1;

  for (const [intIndex, strPathPart] of arrPathParts.entries()) {
    const strNameWithoutExt =
      intIndex === intLastPathPartIndex ? path.parse(strPathPart).name : strPathPart;

    if (!REGEX_PYTHON_PATH_NAME.test(strNameWithoutExt)) {
      throw new Error(
        `Invalid Python file or folder name "${strNameWithoutExt}" in path: ${pyFile}`,
      );
    }

    if (SET_RESERVED_WINDOWS_PATH_NAMES.has(strNameWithoutExt.toUpperCase())) {
      throw new Error(
        `Python file or folder name "${strNameWithoutExt}" is reserved by Windows.\nPath: ${pyFile}`,
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
