// FileName: executorFiles.ts

import { shell } from "electron";
import fs from "fs";
import path from "path";

import { strDocumentsFolderPath } from "../Config/environment";

export const strExecutorPackageFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA",
  "ExecutorPackage",
);

export function getExecutorPackageFolderPath(name: string, version: string): string {
  const strFolderPath = path.join(strExecutorPackageFolderPath, `${name}_${version}`);
  const strResolvedRoot = path.resolve(strExecutorPackageFolderPath);
  const strResolvedFolder = path.resolve(strFolderPath);
  if (!strResolvedFolder.startsWith(`${strResolvedRoot}${path.sep}`)) {
    throw new Error("Generated Executor Package folder escapes the Package root.");
  }
  return strResolvedFolder;
}

export async function fileOpenFolder(strFolderPath: string): Promise<void> {
  if (!fs.existsSync(strFolderPath) || !fs.statSync(strFolderPath).isDirectory()) {
    throw new Error(`Folder does not exist: ${strFolderPath}`);
  }

  const strErrorMessage = await shell.openPath(strFolderPath);
  if (strErrorMessage !== "") {
    throw new Error(`Failed to open folder '${strFolderPath}': ${strErrorMessage}`);
  }
}
