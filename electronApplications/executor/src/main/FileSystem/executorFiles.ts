import { shell } from "electron";
import fs from "fs";
import path from "path";

import { strDocumentsFolderPath } from "../Config/environment";

export const strExecutorPackageFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA",
  "ExecutorPackage",
);

export function getExecutorPackageFolderPath(strName: string, strVersion: string): string {
  const strFolderPath = path.join(strExecutorPackageFolderPath, `${strName}_${strVersion}`);
  const strResolvedRoot = path.resolve(strExecutorPackageFolderPath);
  const strResolvedFolder = path.resolve(strFolderPath);
  if (!strResolvedFolder.startsWith(`${strResolvedRoot}${path.sep}`)) {
    throw new Error("Generated Executor Package folder escapes the Package root.");
  }
  return strResolvedFolder;
}

export function fileDeleteExecutorPackage(strName: string, strVersion: string): void {
  const strExecutorPackagePath = getExecutorPackageFolderPath(strName, strVersion);
  fs.rmSync(strExecutorPackagePath, { recursive: true, force: true });
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
