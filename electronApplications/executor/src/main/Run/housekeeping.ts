// FileName: housekeeping.ts

import { getErrorMessage } from "../../shared/error";
import { dictConfigExecutor } from "../Config/executorConfig";
import { loggerMain } from "../Logging/logger";
import {
  deleteExpiredRunLogs,
  deleteExpiredRunVideos,
  enforceVideoStorageLimit,
} from "./logCleanup";

const INT_CLEANUP_INTERVAL_MS = 60 * 60 * 1000;

let timerCleanup: NodeJS.Timeout | undefined;
let promiseCleanup: Promise<void> | undefined;

function runHousekeeping(): void {
  if (promiseCleanup !== undefined) return;

  if (
    !dictConfigExecutor.logRetentionEnabled &&
    !dictConfigExecutor.videoRetentionEnabled &&
    !dictConfigExecutor.videoStorageLimitEnabled
  ) {
    loggerMain.debug("No log or video files need cleanup.");
    return;
  }

  promiseCleanup = (async () => {
    try {
      if (dictConfigExecutor.logRetentionEnabled) {
        await deleteExpiredRunLogs(dictConfigExecutor.logRetentionDays);
      }
      if (dictConfigExecutor.videoRetentionEnabled) {
        await deleteExpiredRunVideos(dictConfigExecutor.videoRetentionDays);
      }
      if (dictConfigExecutor.videoStorageLimitEnabled) {
        await enforceVideoStorageLimit(dictConfigExecutor.videoStorageLimitGiB);
      }
    } catch (e: unknown) {
      loggerMain.error(`Run housekeeping failed: ${getErrorMessage(e)}`);
    }
  })().finally(() => {
    promiseCleanup = undefined;
  });
}

export function startRunHousekeeping(): void {
  if (timerCleanup !== undefined) {
    return;
  }

  runHousekeeping();
  timerCleanup = setInterval(runHousekeeping, INT_CLEANUP_INTERVAL_MS);
}

export async function stopRunHousekeeping(): Promise<void> {
  if (timerCleanup !== undefined) {
    clearInterval(timerCleanup);
    timerCleanup = undefined;
  }
  await promiseCleanup;
}
