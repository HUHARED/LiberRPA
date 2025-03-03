// FileName: initLiberRPA.ts
import { loggerMain } from "./logger.js";
import path from "path";
import fs from "fs";
import { app } from "electron";
import { getBasicConfigDict } from "./commonFunc.js";

// Set the userData path, not save data in "C:\Users\user\AppData\Roaming\".
const documentsFolderPath = app.getPath("documents");
app.setPath("userData", path.join(documentsFolderPath, "LiberRPA/AppData/ui-analyzer/"));

// Get Flask server port.
export let intLocalServerPort: number;
export let strTheme: string;
export let boolMinimizeWindow: boolean;

try {
  const dictSettings = getBasicConfigDict();

  try {
    // Get Local Server port.
    intLocalServerPort = parseInt(dictSettings["localServerPort"]);
    if (intLocalServerPort) {
      loggerMain.debug(`intLocalServerPort=${intLocalServerPort}`);
    } else {
      throw new Error("'localServerPort' not found in settings.");
    }

    // Get theme setting
    strTheme = dictSettings["uiAnalyzerTheme"];
    if (strTheme) {
      loggerMain.debug(`strTheme=${strTheme}`);
    } else {
      throw new Error("'uiAnalyzerTheme' not found in settings.");
    }

    // Get minimizeWindow setting
    boolMinimizeWindow = JSON.parse(dictSettings["uiAnalyzerMinimizeWindow"]) as boolean;
    if (boolMinimizeWindow !== undefined) {
      loggerMain.debug(`uiAnalyzerMinimizeWindow=${boolMinimizeWindow}`);
    } else {
      throw new Error("'uiAnalyzerMinimizeWindow' not found in settings.");
    }
  } catch (e) {
    throw new Error(`Error reading or parsing file: ${e}`);
  }
} catch (e) {
  loggerMain.error(e);
  app.quit();
}

/* Delete files from 7 days ago in "user\Documents\LiberRPA\Screenshot" */
const strScreenshotPath = path.join(documentsFolderPath, "LiberRPA/Screenshot");
const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds

if (!fs.existsSync(strScreenshotPath)) {
  loggerMain.error(`The folder ${strScreenshotPath} does not exist.`);
} else {
  fs.readdir(strScreenshotPath, (err, files) => {
    if (err) {
      loggerMain.error(`Failed to read the Screenshot folder: ${err.message}`);
      return;
    }
    files.forEach((strFileName) => {
      const strFilePath = path.join(strScreenshotPath, strFileName);

      // Check if it's a file
      fs.stat(strFilePath, (err, stats) => {
        if (err) {
          loggerMain.error(`Failed to get stats for file ${strFilePath}: ${err.message}`);
          return;
        }

        // Check if the file is older than 7 days
        if (stats.isFile() && stats.mtime.getTime() < sevenDaysAgo) {
          // Delete the file
          fs.unlink(strFilePath, (err) => {
            if (err) {
              loggerMain.error(`Failed to delete file ${strFilePath}: ${err.message}`);
            } else {
              loggerMain.info(`Deleted file: ${strFilePath}`);
            }
          });
        }
      });
    });
  });
}
