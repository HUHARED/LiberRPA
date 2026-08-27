// FileName: logPath.ts

import path from "path";

export function ensureRunLogFolderPath(logFolderPath: string, logRootPath: string): string {
  const strResolvedRootPath = path.resolve(logRootPath);
  const strResolvedLogFolderPath = path.resolve(logFolderPath);
  const strRelativePath = path.relative(strResolvedRootPath, strResolvedLogFolderPath);

  if (
    strRelativePath === "" ||
    strRelativePath === ".." ||
    strRelativePath.startsWith(`..${path.sep}`) ||
    path.isAbsolute(strRelativePath)
  ) {
    throw new Error(
      `Executor run log folder must be a child of the configured Project log folder: ${logFolderPath}`,
    );
  }

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
