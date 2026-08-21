// FileName: logCleanFunc.ts

import fs from "fs";
import path from "path";

import {
  dbSelectLogFolderBefore,
  dbSelectVideo,
  dbSelectVideoBefore,
  dbUpdateNoLogFolderAndVideo,
  dbUpdateNoVideo,
} from "./database";
import { loggerMain } from "./logger";

const INT_MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000;

export function logCleanFolderByTimeout(intTimeoutDays: number): void {
  const intCutoffMs = Date.now() - intTimeoutDays * INT_MILLISECONDS_PER_DAY;
  const arrLogFolderPath = dbSelectLogFolderBefore(intCutoffMs);

  for (const strLogFolderPath of arrLogFolderPath) {
    try {
      if (fs.existsSync(strLogFolderPath) && fs.statSync(strLogFolderPath).isDirectory()) {
        loggerMain.info(`Delete log folder: ${strLogFolderPath}`);
        fs.rmSync(strLogFolderPath, { recursive: true });
      } else {
        loggerMain.debug(`No log folder: ${strLogFolderPath}`);
      }

      dbUpdateNoLogFolderAndVideo(strLogFolderPath);
    } catch (e: unknown) {
      loggerMain.error(e);
    }
  }
}

export function logCleanVideoByTimeout(intTimeoutDays: number): void {
  const intCutoffMs = Date.now() - intTimeoutDays * INT_MILLISECONDS_PER_DAY;
  const arrLogFolderPath = dbSelectVideoBefore(intCutoffMs);

  for (const strLogFolderPath of arrLogFolderPath) {
    try {
      const strVideoFilePath = path.join(strLogFolderPath, "video_record.mkv");
      const strSubtitleFilePath = path.join(strLogFolderPath, "video_record.srt");

      if (
        fs.existsSync(strLogFolderPath) &&
        fs.statSync(strLogFolderPath).isDirectory() &&
        fs.existsSync(strVideoFilePath) &&
        fs.statSync(strVideoFilePath).isFile()
      ) {
        loggerMain.info(`Delete video and subtitle in folder: ${strLogFolderPath}`);
        fs.unlinkSync(strVideoFilePath);

        if (
          fs.existsSync(strSubtitleFilePath) &&
          fs.statSync(strSubtitleFilePath).isFile()
        ) {
          fs.unlinkSync(strSubtitleFilePath);
        }
      } else {
        loggerMain.debug(`No video: ${strLogFolderPath}`);
      }

      dbUpdateNoVideo(strLogFolderPath);
    } catch (e: unknown) {
      loggerMain.error(e);
    }
  }
}

export function logCleanVideoBySize(intSizeGb: number): void {
  let floatSizeGbTotal = 0;
  const arrLogFolderPath = dbSelectVideo();

  for (const strLogFolderPath of arrLogFolderPath) {
    try {
      const strVideoFilePath = path.join(strLogFolderPath, "video_record.mkv");
      const strSubtitleFilePath = path.join(strLogFolderPath, "video_record.srt");

      if (
        fs.existsSync(strLogFolderPath) &&
        fs.statSync(strLogFolderPath).isDirectory() &&
        fs.existsSync(strVideoFilePath) &&
        fs.statSync(strVideoFilePath).isFile()
      ) {
        const floatVideoSizeGb = fs.statSync(strVideoFilePath).size / 1024 ** 3;
        if (floatSizeGbTotal + floatVideoSizeGb <= intSizeGb) {
          floatSizeGbTotal += floatVideoSizeGb;
          loggerMain.debug(`Video size total: ${floatSizeGbTotal} GB`);
          continue;
        }

        loggerMain.info(`Delete video and subtitle in folder: ${strLogFolderPath}`);
        fs.unlinkSync(strVideoFilePath);

        if (
          fs.existsSync(strSubtitleFilePath) &&
          fs.statSync(strSubtitleFilePath).isFile()
        ) {
          fs.unlinkSync(strSubtitleFilePath);
        }
        dbUpdateNoVideo(strLogFolderPath);
      } else {
        loggerMain.debug(`No video: ${strLogFolderPath}`);
        dbUpdateNoVideo(strLogFolderPath);
      }
    } catch (e: unknown) {
      loggerMain.error(e);
    }
  }
}
