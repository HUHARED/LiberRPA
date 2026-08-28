// FileName: housekeeping.ts

import { dictConfigExecutor } from "../Config/executorConfig";
import { loggerMain } from "../Logging/logger";
import {
  logCleanFolderByTimeout,
  logCleanVideoBySize,
  logCleanVideoByTimeout,
} from "./logCleanup";

const INT_CLEANUP_INTERVAL_MS = 60 * 60 * 1000;

let timerCleanup: NodeJS.Timeout | undefined;

function runHousekeeping(): void {
  if (
    !dictConfigExecutor.logTimeoutEnable &&
    !dictConfigExecutor.videoTimeoutEnable &&
    !dictConfigExecutor.videoSizeEnable
  ) {
    loggerMain.debug("No log or video files need cleanup.");
    return;
  }

  try {
    if (dictConfigExecutor.logTimeoutEnable) {
      logCleanFolderByTimeout(dictConfigExecutor.logTimeoutDays);
    }
    if (dictConfigExecutor.videoTimeoutEnable) {
      logCleanVideoByTimeout(dictConfigExecutor.videoTimeoutDays);
    }
    if (dictConfigExecutor.videoSizeEnable) {
      logCleanVideoBySize(dictConfigExecutor.videoSizeGB);
    }
  } catch (e: unknown) {
    loggerMain.error(
      `Run housekeeping failed: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
}

export function startRunHousekeeping(): void {
  if (timerCleanup !== undefined) {
    return;
  }

  runHousekeeping();
  timerCleanup = setInterval(runHousekeeping, INT_CLEANUP_INTERVAL_MS);
}

export function stopRunHousekeeping(): void {
  if (timerCleanup === undefined) {
    return;
  }

  clearInterval(timerCleanup);
  timerCleanup = undefined;
}
