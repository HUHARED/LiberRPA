import { dictConfigExecutor } from "../Config/config";
import {
  logCleanFolderByTimeout,
  logCleanVideoBySize,
  logCleanVideoByTimeout,
} from "./logCleanup";
import { loggerMain } from "../Logging/logger";
import { onRunEnded } from "./lifecycle";

const INT_CLEANUP_INTERVAL_MS = 60 * 60 * 1000;

let intLastCleanupAtMs = Date.now();
let boolStarted = false;

export function startRunHousekeeping(): void {
  if (boolStarted) {
    return;
  }

  boolStarted = true;
  onRunEnded(handleRunEndedHousekeeping);
}

function handleRunEndedHousekeeping(): void {
  if (
    !dictConfigExecutor.logTimeoutEnable &&
    !dictConfigExecutor.videoTimeoutEnable &&
    !dictConfigExecutor.videoSizeEnable
  ) {
    loggerMain.debug("No log or video files need cleanup.");
    return;
  }

  const intNowMs = Date.now();
  if (intNowMs - intLastCleanupAtMs < INT_CLEANUP_INTERVAL_MS) {
    return;
  }

  intLastCleanupAtMs = intNowMs;

  if (dictConfigExecutor.logTimeoutEnable) {
    logCleanFolderByTimeout(dictConfigExecutor.logTimeoutDays);
  }
  if (dictConfigExecutor.videoTimeoutEnable) {
    logCleanVideoByTimeout(dictConfigExecutor.videoTimeoutDays);
  }
  if (dictConfigExecutor.videoSizeEnable) {
    logCleanVideoBySize(dictConfigExecutor.videoSizeGB);
  }
}
