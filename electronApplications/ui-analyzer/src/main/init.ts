// FileName: init.ts

import fs from "fs/promises";
import path from "path";
import type { Logger } from "winston";

import { getErrorMessage } from "../shared/error";

const INT_SCREENSHOT_RETENTION_MS = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds

function isFileNotFoundError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === "ENOENT"
  );
}

export async function deleteExpiredScreenshots(
  strDocumentsFolderPath: string,
  loggerMain: Logger,
): Promise<void> {
  const strScreenshotFolderPath = path.join(
    strDocumentsFolderPath,
    "LiberRPA",
    "Screenshots",
  );
  const intExpiredBeforeMs = Date.now() - INT_SCREENSHOT_RETENTION_MS;

  let arrFileName: string[];
  try {
    arrFileName = await fs.readdir(strScreenshotFolderPath);
  } catch (e: unknown) {
    if (isFileNotFoundError(e)) {
      loggerMain.debug(`Screenshots folder does not exist: ${strScreenshotFolderPath}`);
      return;
    }

    loggerMain.error(
      `Failed to read the Screenshots folder ${strScreenshotFolderPath}: ${getErrorMessage(e)}`,
    );
    return;
  }

  for (const strFileName of arrFileName) {
    const strFilePath = path.join(strScreenshotFolderPath, strFileName);

    try {
      const fileStat = await fs.stat(strFilePath);
      if (!fileStat.isFile() || fileStat.mtimeMs >= intExpiredBeforeMs) {
        continue;
      }

      await fs.unlink(strFilePath);
      loggerMain.info(`Deleted expired screenshot: ${strFilePath}`);
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to process screenshot file ${strFilePath}: ${getErrorMessage(e)}`,
      );
    }
  }
}
