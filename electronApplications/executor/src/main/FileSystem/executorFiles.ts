// FileName: executorFiles.ts

import { shell } from "electron";
import fs from "fs";
import path from "path";

import { getWindowsFolderNameError } from "../Common/validation";
import { strDocumentsFolderPath } from "../Config/environment";

export const strPackageRootPath = path.join(strDocumentsFolderPath, "LiberRPA", "Packages");
export const strLocalPackageRootPath = path.join(strPackageRootPath, "Local");
export const strConsolePackageRootPath = path.join(strPackageRootPath, "Console");

export function getPackageFolderName(
  projectName: string,
  projectVersion: string,
  consolePackageId?: string,
): string {
  const strFolderName =
    `${projectName}_${projectVersion}` +
    (consolePackageId === undefined ? "" : `_${consolePackageId}`);
  const strError = getWindowsFolderNameError(strFolderName);
  if (strError !== undefined) {
    throw new Error(`Cannot create the Flow Package folder name: ${strError}`);
  }
  return strFolderName;
}

export function getLocalPackageFolderPath(
  projectName: string,
  projectVersion: string,
): string {
  return path.join(
    strLocalPackageRootPath,
    getPackageFolderName(projectName, projectVersion),
  );
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
