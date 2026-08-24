import path from "path";

export function ensureRunLogFolderPath(
  strLogFolderPath: string,
  strLogRootPath: string,
): string {
  const strResolvedRootPath = path.resolve(strLogRootPath);
  const strResolvedLogFolderPath = path.resolve(strLogFolderPath);
  const strRelativePath = path.relative(strResolvedRootPath, strResolvedLogFolderPath);

  if (
    strRelativePath === "" ||
    strRelativePath === ".." ||
    strRelativePath.startsWith(`..${path.sep}`) ||
    path.isAbsolute(strRelativePath)
  ) {
    throw new Error(
      `Executor run log folder must be a child of the configured Project log folder: ${strLogFolderPath}`,
    );
  }

  return strResolvedLogFolderPath;
}

export function ensureExpectedRunLogFolderPath(
  strLogFolderPath: string,
  strExpectedLogFolderPath: string,
): string {
  const strResolvedLogFolderPath = path.resolve(strLogFolderPath);
  const strResolvedExpectedLogFolderPath = path.resolve(strExpectedLogFolderPath);

  if (path.relative(strResolvedExpectedLogFolderPath, strResolvedLogFolderPath) !== "") {
    throw new Error(`Executor run state changed logPath unexpectedly: ${strLogFolderPath}`);
  }

  return strResolvedLogFolderPath;
}
