// FileName: logCleanup.ts

import fs from "fs";
import path from "path";

import { RunRecordingStatus } from "../../shared/run";
import { getErrorMessage } from "../../shared/error";
import {
  type RunLogLocation,
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

async function deleteVideoFiles(logFolderPath: string): Promise<boolean> {
  const strVideoFilePath = getExistingLogFilePath(logFolderPath, STR_VIDEO_FILE_NAME);
  const strSubtitleFilePath = getExistingLogFilePath(logFolderPath, STR_SUBTITLE_FILE_NAME);

  if (strVideoFilePath === undefined) {
    if (strSubtitleFilePath !== undefined) {
      await fs.promises.unlink(strSubtitleFilePath);
    }
    return false;
  }

  await fs.promises.unlink(strVideoFilePath);
  if (strSubtitleFilePath !== undefined) {
    await fs.promises.unlink(strSubtitleFilePath);
  }
  return true;
}

export async function deleteExpiredRunLogs(retentionDays: number): Promise<void> {
  const intCutoffMs = Date.now() - retentionDays * INT_MILLISECONDS_PER_DAY;
  const arrLogLocation = dbSelectLogFolderBefore(intCutoffMs);

  for (const logLocation of arrLogLocation) {
    try {
      if (!canCleanRunRecording(logLocation)) continue;
      const strLogFolderPath = getExistingRunLogFolderPath(logLocation);
      // Stop pending uploads before deletion can expose a partial log directory.
      markConsoleLogsUnavailable(
        logLocation.run_id,
        "The local log retention period ended before upload completed.",
      );
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder: ${logLocation.log_path}`);
      } else {
        loggerMain.info(`Delete log folder: ${strLogFolderPath}`);
        await fs.promises.rm(strLogFolderPath, { recursive: true });
      }

      dbUpdateNoLogFolderAndVideo(logLocation.id);
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to clean Run log folder ${logLocation.log_path}: ${getErrorMessage(e)}`,
      );
    }
  }
}

export async function deleteExpiredRunVideos(retentionDays: number): Promise<void> {
  const intCutoffMs = Date.now() - retentionDays * INT_MILLISECONDS_PER_DAY;
  const arrLogLocation = dbSelectVideoBefore(intCutoffMs);

  for (const logLocation of arrLogLocation) {
    try {
      if (!canCleanRunRecording(logLocation)) continue;
      const strLogFolderPath = getExistingRunLogFolderPath(logLocation);
      if (strLogFolderPath === undefined) {
        loggerMain.debug(`No log folder for video: ${logLocation.log_path}`);
      } else if (await deleteVideoFiles(strLogFolderPath)) {
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

export async function enforceVideoStorageLimit(storageLimitGiB: number): Promise<void> {
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
        await deleteVideoFiles(strLogFolderPath);
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

      await deleteVideoFiles(strLogFolderPath);
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
