// FileName: init.ts
import path from "path";
import fs from "fs";

import { loggerMain } from "./logger";
import { strDocumentsFolderPath } from "./config";

export function deleteTimeoutScreenshot(): void {
  // Delete files from 7 days ago in "user/Documents/LiberRPA/Screenshot"

  const strScreenshotPath = path.join(strDocumentsFolderPath, "LiberRPA/Screenshot");
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds

  if (!fs.existsSync(strScreenshotPath)) {
    loggerMain.error(`The folder ${strScreenshotPath} does not exist.`);
    return;
  }

  let arrFiles: string[];

  try {
    arrFiles = fs.readdirSync(strScreenshotPath);
  } catch (e) {
    loggerMain.error(`Failed to read the Screenshot folder: ${e}`);
    return;
  }

  for (const file of arrFiles) {
    const strFilePath = path.join(strScreenshotPath, file);

    if (
      fs.statSync(strFilePath).isFile() &&
      fs.statSync(strFilePath).mtime.getTime() < sevenDaysAgo
    ) {
      try {
        fs.unlinkSync(strFilePath);
        loggerMain.info(`Deleted file: ${strFilePath}`);
      } catch (e) {
        loggerMain.error(`Failed to delete file ${strFilePath}: ${e}`);
      }
    }
  }
}
