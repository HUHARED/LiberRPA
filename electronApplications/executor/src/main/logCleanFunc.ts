// FileName: logCleanFunc.ts
import path from "path";
import fs from "fs";

import { loggerMain } from "./logger";
import {
  dbSelect_LogFolder_ByTimeout,
  dbSelect_Video_ByTimeout,
  dbSelect_Video,
  dbUpdate_NoLogFolderAndVideo,
  dbUpdate_NoVideo,
} from "./database";

export function logCleanFolderByTimeout(timeoutDays: number): void {
  const arrLogFolderPath = dbSelect_LogFolder_ByTimeout(timeoutDays);
  for (const item of arrLogFolderPath) {
    try {
      if (fs.existsSync(item) && fs.statSync(item).isDirectory()) {
        loggerMain.info(`Delete log folder: ${item}`);
        fs.rmSync(item, { recursive: true });
      } else {
        loggerMain.debug(`No log folder: ${item}`);
      }

      dbUpdate_NoLogFolderAndVideo(item);
    } catch (e) {
      loggerMain.error(e);
    }
  }
}

export function logCleanVideoByTimeout(timeoutDays: number): void {
  const arrLogFolderPath = dbSelect_Video_ByTimeout(timeoutDays);
  for (const item of arrLogFolderPath) {
    try {
      const strVideoFilePath = path.join(item, "video_record.mkv");
      const strSubtitleFilePath = path.join(item, "video_record.srt");
      if (
        fs.existsSync(item) &&
        fs.statSync(item).isDirectory() &&
        fs.existsSync(strVideoFilePath) &&
        fs.statSync(strVideoFilePath).isFile()
      ) {
        loggerMain.info(`Delete video and subtitle in folder: ${item}`);
        fs.unlinkSync(strVideoFilePath);

        if (
          fs.existsSync(strSubtitleFilePath) &&
          fs.statSync(strSubtitleFilePath).isFile()
        ) {
          fs.unlinkSync(strSubtitleFilePath);
        }
      } else {
        loggerMain.debug(`No video: ${item}`);
      }

      dbUpdate_NoVideo(item);
    } catch (e) {
      loggerMain.error(e);
    }
  }
}

export function logCleanVideoBySize(size: number): void {
  let sizeGbTotal = 0;

  const arrLogFolderPath = dbSelect_Video();
  for (const item of arrLogFolderPath) {
    try {
      const strVideoFilePath = path.join(item, "video_record.mkv");
      const strSubtitleFilePath = path.join(item, "video_record.srt");
      if (
        fs.existsSync(item) &&
        fs.statSync(item).isDirectory() &&
        fs.existsSync(strVideoFilePath) &&
        fs.statSync(strVideoFilePath).isFile()
      ) {
        const sizeGbTemp = fs.statSync(strVideoFilePath).size / 1024 ** 3;
        if (sizeGbTotal + sizeGbTemp <= size) {
          sizeGbTotal += sizeGbTemp;
          loggerMain.debug(`Video size total: ${sizeGbTotal} GB`);
        } else {
          // Delete the video and subtitle.
          loggerMain.info(`Delete video and subtitle in folder: ${item}`);
          fs.unlinkSync(strVideoFilePath);

          if (
            fs.existsSync(strSubtitleFilePath) &&
            fs.statSync(strSubtitleFilePath).isFile()
          ) {
            fs.unlinkSync(strSubtitleFilePath);
          }
          dbUpdate_NoVideo(item);
        }
      } else {
        loggerMain.debug(`No video: ${item}`);
        dbUpdate_NoVideo(item);
      }
    } catch (e) {
      loggerMain.error(e);
    }
  }
}
