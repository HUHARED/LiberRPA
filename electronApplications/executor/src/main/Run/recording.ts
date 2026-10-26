// FileName: recording.ts

import fs from "fs";
import path from "path";

import { RunRecordingStatus, type RunRecordingInfo } from "../../shared/run";
import {
  ensureExactRecord,
  ensureString,
  ensureNullableNonNegativeInteger,
} from "../Common/validation";

const INT_RECORDING_START_GRACE_MS = 60_000;

function isRunRecordingActive(logFolderPath: string): boolean {
  let intFd: number | undefined;
  try {
    intFd = fs.openSync(path.join(logFolderPath, "video_record.lock"), "r");
    // NOTE: _Record.py holds an exclusive Windows byte lock until video merging and subtitle creation have finished.
    fs.readSync(intFd, Buffer.alloc(1), 0, 1, 0);
    return false;
  } catch (e: unknown) {
    if (e instanceof Error && "code" in e) {
      if (e.code === "ENOENT") return false;
      if (e.code === "EBUSY") return true;
    }
    // A permission or I/O failure is not evidence that recording has ended.
    throw e;
  } finally {
    if (intFd !== undefined) fs.closeSync(intFd);
  }
}

export function readRunRecording(
  logFolderPath: string,
  processExitConfirmedAtMs: number,
): RunRecordingInfo | undefined {
  const boolActive = isRunRecordingActive(logFolderPath);
  let value: unknown;
  try {
    value = JSON.parse(
      fs.readFileSync(path.join(logFolderPath, "video_record.state.json"), "utf8"),
    ) as unknown;
  } catch (e: unknown) {
    if (!(e instanceof Error && "code" in e && e.code === "ENOENT")) throw e;
    // NOTE: Recovery may supply the exit observation time because the actual Run end time is unknown.
    if (boolActive || Date.now() - processExitConfirmedAtMs < INT_RECORDING_START_GRACE_MS)
      return undefined;
    return {
      status: RunRecordingStatus.Unavailable,
      videoSizeBytes: null,
      subtitleSizeBytes: null,
      reason: "Recording did not start.",
    };
  }
  const recording = ensureExactRecord(
    value,
    ["status", "videoSizeBytes", "subtitleSizeBytes", "reason"],
    "Recording state",
  );
  const status = Object.values(RunRecordingStatus).find(
    (status) => status === recording.status,
  );
  if (status === undefined) throw new Error("Recording state has an unsupported status.");
  const strReason = ensureString(recording.reason, "Recording reason");
  if ([...strReason].length > 2000)
    throw new Error("Recording reason cannot exceed 2000 characters.");
  const result: RunRecordingInfo = {
    status,
    videoSizeBytes: ensureNullableNonNegativeInteger(
      recording.videoSizeBytes,
      "Recording video size",
    ),
    subtitleSizeBytes: ensureNullableNonNegativeInteger(
      recording.subtitleSizeBytes,
      "Recording subtitle size",
    ),
    reason: strReason,
  };
  if (
    !boolActive &&
    (status === RunRecordingStatus.Recording || status === RunRecordingStatus.Processing)
  ) {
    return {
      status: RunRecordingStatus.Unavailable,
      videoSizeBytes: null,
      subtitleSizeBytes: null,
      reason: "Video recording was interrupted.",
    };
  }
  return result;
}
