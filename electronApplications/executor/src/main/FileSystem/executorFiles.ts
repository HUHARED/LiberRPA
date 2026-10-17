// FileName: executorFiles.ts

import { shell } from "electron";
import fs from "fs";
import path from "path";

import { strDocumentsFolderPath } from "../Config/environment";
import { getPackageFolderName } from "../Package/packageArchive";

export const strPackageFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA",
  "Packages",
);
export const strLocalPackageFolderPath = path.join(strPackageFolderPath, "Local");
export const strConsolePackageFolderPath = path.join(strPackageFolderPath, "Console");

export function getLocalPackageFolderPath(
  projectName: string,
  projectVersion: string,
): string {
  return path.join(
    strLocalPackageFolderPath,
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
