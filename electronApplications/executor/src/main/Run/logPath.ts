// FileName: logPath.ts

import fs from "fs";
import path from "path";

function ensureChildPath(childPath: string, parentPath: string, sourceName: string): void {
  const strRelativePath = path.relative(parentPath, childPath);
  if (
    strRelativePath === "" ||
    strRelativePath === ".." ||
    strRelativePath.startsWith(`..${path.sep}`) ||
    path.isAbsolute(strRelativePath)
  ) {
    throw new Error(
      `${sourceName} must be a child of the Project log folder: ${childPath}`,
    );
  }
}

export function ensureRunLogFolderPath(logFolderPath: string, logRootPath: string): string {
  const strResolvedRootPath = path.resolve(logRootPath);
  const strResolvedLogFolderPath = path.resolve(logFolderPath);
  ensureChildPath(strResolvedLogFolderPath, strResolvedRootPath, "Executor run log folder");
  return strResolvedLogFolderPath;
}

export function ensureExistingRunLogFolderPath(
  logFolderPath: string,
  logRootPath: string,
): string {
  const strResolvedRootPath = path.resolve(logRootPath);
  const strResolvedLogFolderPath = ensureRunLogFolderPath(
    logFolderPath,
    strResolvedRootPath,
  );

  const rootStat = fs.statSync(strResolvedRootPath);
  if (!rootStat.isDirectory()) {
    throw new Error(`Project log root is not a directory: ${strResolvedRootPath}`);
  }

  const logFolderStat = fs.lstatSync(strResolvedLogFolderPath);
  if (logFolderStat.isSymbolicLink() || !logFolderStat.isDirectory()) {
    throw new Error(
      `Executor run log folder is not a regular directory: ${strResolvedLogFolderPath}`,
    );
  }

  const strRealRootPath = fs.realpathSync.native(strResolvedRootPath);
  const strRealLogFolderPath = fs.realpathSync.native(strResolvedLogFolderPath);
  ensureChildPath(
    strRealLogFolderPath,
    strRealRootPath,
    "Resolved Executor run log folder",
  );

  return strResolvedLogFolderPath;
}

export function ensureExpectedRunLogFolderPath(
  logFolderPath: string,
  expectedLogFolderPath: string,
): string {
  const strResolvedLogFolderPath = path.resolve(logFolderPath);
  const strResolvedExpectedLogFolderPath = path.resolve(expectedLogFolderPath);

  if (path.relative(strResolvedExpectedLogFolderPath, strResolvedLogFolderPath) !== "") {
    throw new Error(`Executor run state changed logPath unexpectedly: ${logFolderPath}`);
  }

  return strResolvedLogFolderPath;
}
