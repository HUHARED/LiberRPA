// FileName: logCleanup.ts

import fs from "fs";
import path from "path";

import type { Dict_RunHistory_LogLocation } from "../Database/rowValidation";
import {
  dbSelectLogFolderBefore,
  dbSelectVideo,
  dbSelectVideoBefore,
  dbUpdateNoLogFolderAndVideo,
  dbUpdateNoVideo,
} from "../Database/runHistoryRepository";
import { loggerMain } from "../Logging/logger";
import { ensureExistingRunLogFolderPath } from "./logPath";

const INT_MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000;
const STR_VIDEO_FILE_NAME = "video_record.mkv";
const STR_SUBTITLE_FILE_NAME = "video_record.srt";

function getRegularFilePath(folderPath: string, fileName: string): string | undefined {
  const strFilePath = path.join(folderPath, fileName);
  if (!fs.existsSync(strFilePath)) {
    return undefined;
  }

  const fileStat = fs.lstatSync(strFilePath);
  if (fileStat.isSymbolicLink() || !fileStat.isFile()) {
    throw new Error(`Expected a regular log file: ${strFilePath}`);
  }
  return strFilePath;
}

function getValidatedLogFolderPath(
  logLocation: Dict_RunHistory_LogLocation,
): string | undefined {
  if (!fs.existsSync(logLocation.log_path)) {
    return undefined;
  }
  return ensureExistingRunLogFolderPath(logLocation.log_path, logLocation.log_root_path);
}

function deleteVideoFiles(logFolderPath: string): boolean {
  const strVideoFilePath = getRegularFilePath(logFolderPath, STR_VIDEO_FILE_NAME);
  const strSubtitleFilePath = getRegularFilePath(logFolderPath, STR_SUBTITLE_FILE_NAME);

  if (strVideoFilePath === undefined) {
    if (strSubtitleFilePath !== undefined) {
      fs.unlinkSync(strSubtitleFilePath);
    }
    return false;
  }

  fs.unlinkSync(strVideoFilePath);
  if (strSubtitleFilePath !== undefined) {
    fs.unlinkSync(strSubtitleFilePath);
  }
  return true;
}

export function logCleanFolderByTimeout(timeoutDays: number): void {
  const intCutoffMs = Date.now() - timeoutDays * INT_MILLISECONDS_PER_DAY;
  const arrLogLocation = dbSelectLogFolderBefore(intCutoffMs);

  for (const logLocation of arrLogLocation) {
    try {
      const strLogFolderPath = getValidatedLogFolderPath(logLocation);
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder: ${logLocation.log_path}`);
      } else {
        loggerMain.info(`Delete log folder: ${strLogFolderPath}`);
        fs.rmSync(strLogFolderPath, { recursive: true });
      }

      dbUpdateNoLogFolderAndVideo(logLocation.id);
    } catch (e: unknown) {
      loggerMain.error(e);
    }
  }
}

export function logCleanVideoByTimeout(timeoutDays: number): void {
  const intCutoffMs = Date.now() - timeoutDays * INT_MILLISECONDS_PER_DAY;
  const arrLogLocation = dbSelectVideoBefore(intCutoffMs);

  for (const logLocation of arrLogLocation) {
    try {
      const strLogFolderPath = getValidatedLogFolderPath(logLocation);
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder for video: ${logLocation.log_path}`);
      } else if (deleteVideoFiles(strLogFolderPath)) {
        loggerMain.info(`Deleted video and subtitle in folder: ${strLogFolderPath}`);
      } else {
        loggerMain.debug(`No video: ${strLogFolderPath}`);
      }

      dbUpdateNoVideo(logLocation.id);
    } catch (e: unknown) {
      loggerMain.error(e);
    }
  }
}

export function logCleanVideoBySize(sizeGb: number): void {
  let floatSizeGbTotal = 0;
  const arrLogLocation = dbSelectVideo();

  for (const logLocation of arrLogLocation) {
    try {
      const strLogFolderPath = getValidatedLogFolderPath(logLocation);
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder for video: ${logLocation.log_path}`);
        dbUpdateNoVideo(logLocation.id);
        continue;
      }

      const strVideoFilePath = getRegularFilePath(strLogFolderPath, STR_VIDEO_FILE_NAME);
      if (strVideoFilePath === undefined) {
        deleteVideoFiles(strLogFolderPath);
        loggerMain.debug(`No video: ${strLogFolderPath}`);
        dbUpdateNoVideo(logLocation.id);
        continue;
      }

      const floatVideoSizeGb = fs.statSync(strVideoFilePath).size / 1024 ** 3;
      if (floatSizeGbTotal + floatVideoSizeGb <= sizeGb) {
        floatSizeGbTotal += floatVideoSizeGb;
        loggerMain.debug(`Video size total: ${floatSizeGbTotal} GB`);
        continue;
      }

      deleteVideoFiles(strLogFolderPath);
      loggerMain.info(`Deleted video and subtitle in folder: ${strLogFolderPath}`);
      dbUpdateNoVideo(logLocation.id);
    } catch (e: unknown) {
      loggerMain.error(e);
    }
  }
}
