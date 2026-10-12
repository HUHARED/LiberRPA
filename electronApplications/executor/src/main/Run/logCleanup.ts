// FileName: logCleanup.ts

import fs from "fs";
import path from "path";

import { RunRecordingStatus } from "../../shared/run";
import { getErrorMessage } from "../../shared/error";
import type { RunLogLocation } from "../Database/rowValidation";
import {
  dbSelectLogFolderBefore,
  dbSelectVideoBefore,
  dbSelectVideo,
  dbUpdateNoLogFolderAndVideo,
  dbUpdateNoVideo,
} from "../Database/runHistoryRepository";
import { loggerMain } from "../Logging/logger";
import { ensureExistingRunLogFolderPath } from "./logPath";
import { readRunRecording } from "./recording";
import { markConsoleLogsUnavailable } from "../Console/workRepository";

const INT_MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000;
const STR_VIDEO_FILE_NAME = "video_record.mkv";
const STR_SUBTITLE_FILE_NAME = "video_record.srt";

function getExistingLogFilePath(folderPath: string, fileName: string): string | undefined {
  const strFilePath = path.join(folderPath, fileName);
  if (!fs.existsSync(strFilePath)) {
    return undefined;
  }

  if (!fs.statSync(strFilePath).isFile()) {
    throw new Error(`Expected a log file: ${strFilePath}`);
  }
  return strFilePath;
}

function getExistingRunLogFolderPath(logLocation: RunLogLocation): string | undefined {
  try {
    fs.statSync(logLocation.log_path);
  } catch (e: unknown) {
    if (e instanceof Error && "code" in e && e.code === "ENOENT") return undefined;
    throw e;
  }
  return ensureExistingRunLogFolderPath(logLocation.log_path);
}

function canCleanRunRecording(logLocation: RunLogLocation): boolean {
  if (!logLocation.record_video) return true;
  const recording = readRunRecording(logLocation.log_path, logLocation.finished_at_ms);
  return (
    recording?.status === RunRecordingStatus.Ready ||
    recording?.status === RunRecordingStatus.Unavailable
  );
}

function deleteVideoFiles(logFolderPath: string): boolean {
  const strVideoFilePath = getExistingLogFilePath(logFolderPath, STR_VIDEO_FILE_NAME);
  const strSubtitleFilePath = getExistingLogFilePath(logFolderPath, STR_SUBTITLE_FILE_NAME);

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

export function deleteExpiredRunLogs(retentionDays: number): void {
  const intCutoffMs = Date.now() - retentionDays * INT_MILLISECONDS_PER_DAY;
  const arrLogLocation = dbSelectLogFolderBefore(intCutoffMs);

  for (const logLocation of arrLogLocation) {
    try {
      if (!canCleanRunRecording(logLocation)) continue;
      const strLogFolderPath = getExistingRunLogFolderPath(logLocation);
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder: ${logLocation.log_path}`);
      } else {
        loggerMain.info(`Delete log folder: ${strLogFolderPath}`);
        fs.rmSync(strLogFolderPath, { recursive: true });
      }

      markConsoleLogsUnavailable(
        logLocation.run_id,
        "The local log retention period ended before upload completed.",
      );
      dbUpdateNoLogFolderAndVideo(logLocation.id);
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to clean Run log folder ${logLocation.log_path}: ${getErrorMessage(e)}`,
      );
    }
  }
}

export function deleteExpiredRunVideos(retentionDays: number): void {
  const intCutoffMs = Date.now() - retentionDays * INT_MILLISECONDS_PER_DAY;
  const arrLogLocation = dbSelectVideoBefore(intCutoffMs);

  for (const logLocation of arrLogLocation) {
    try {
      if (!canCleanRunRecording(logLocation)) continue;
      const strLogFolderPath = getExistingRunLogFolderPath(logLocation);
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder for video: ${logLocation.log_path}`);
      } else if (deleteVideoFiles(strLogFolderPath)) {
        loggerMain.info(`Deleted video and subtitle in folder: ${strLogFolderPath}`);
      } else {
        loggerMain.debug(`No video: ${strLogFolderPath}`);
      }

      dbUpdateNoVideo(logLocation.id);
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to clean expired Run video in ${logLocation.log_path}: ${getErrorMessage(e)}`,
      );
    }
  }
}

export function enforceVideoStorageLimit(storageLimitGiB: number): void {
  let floatTotalSizeGiB = 0;
  const arrLogLocation = dbSelectVideo();

  for (const logLocation of arrLogLocation) {
    try {
      if (!canCleanRunRecording(logLocation)) continue;
      const strLogFolderPath = getExistingRunLogFolderPath(logLocation);
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder for video: ${logLocation.log_path}`);
        dbUpdateNoVideo(logLocation.id);
        continue;
      }

      const strVideoFilePath = getExistingLogFilePath(
        strLogFolderPath,
        STR_VIDEO_FILE_NAME,
      );
      if (strVideoFilePath === undefined) {
        deleteVideoFiles(strLogFolderPath);
        loggerMain.debug(`No video: ${strLogFolderPath}`);
        dbUpdateNoVideo(logLocation.id);
        continue;
      }

      const floatVideoSizeGiB = fs.statSync(strVideoFilePath).size / 1024 ** 3;
      if (floatTotalSizeGiB + floatVideoSizeGiB <= storageLimitGiB) {
        floatTotalSizeGiB += floatVideoSizeGiB;
        loggerMain.debug(`Video size total: ${floatTotalSizeGiB} GiB`);
        continue;
      }

      deleteVideoFiles(strLogFolderPath);
      loggerMain.info(`Deleted video and subtitle in folder: ${strLogFolderPath}`);
      dbUpdateNoVideo(logLocation.id);
    } catch (e: unknown) {
      loggerMain.error(
        "Failed to enforce the Run video size limit for " +
          `${logLocation.log_path}: ${getErrorMessage(e)}`,
      );
    }
  }
}
