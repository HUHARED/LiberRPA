// FileName: consoleLogs.ts

import fs from "fs";
import path from "path";
import { performance } from "perf_hooks";

import { RunRecordingStatus } from "../../shared/run";
import { getErrorMessage } from "../../shared/error";
import { ensureRecord, ensureNonEmptyString } from "../Common/validation";
import { loggerMain } from "../Logging/logger";
import { ensureExistingRunLogFolderPath } from "../Run/logPath";
import { readRunRecording } from "../Run/recording";
import { ConsoleRequestError, requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  type ConsoleWorkRecord,
  getConsoleWork,
  getPendingConsoleLogWork,
  saveConsoleLogProgress,
  reportConsoleRecording,
} from "./workRepository";

const abortLogs = new AbortController();

export function stopConsoleLogs(): void {
  abortLogs.abort();
}

const INT_LOG_READ_BYTES = 64 * 1024;
const INT_LOG_ENTRY_BYTES = 256 * 1024;
const INT_LOG_BATCH_BYTES = 1024 * 1024;
const INT_LOG_BATCH_ENTRIES = 500;

interface LogBatch {
  fileKey: string;
  startOffset: number;
  logs: string[];
  nextOffset: number;
  atEnd: boolean;
  skipped: { offset: number; reason: string }[];
}

const mapLogRetry = new Map<string, { nextAt: number; delayMs: number }>();
const mapLogSessionRetryAt = new Map<string, number>();

async function readLogBatch(
  filePath: string,
  offsets: Record<string, number>,
  ended: boolean,
): Promise<LogBatch> {
  const fileObj = await fs.promises.open(filePath, "r");
  try {
    const stat = await fileObj.stat();
    const strFileKey = `${stat.dev}:${stat.ino}:${stat.birthtimeMs}`;
    const intSize = stat.size;
    const intStoredOffset = offsets[strFileKey] ?? 0;
    const intOffset = intStoredOffset > intSize ? 0 : intStoredOffset;
    const batch: LogBatch = {
      fileKey: strFileKey,
      startOffset: intOffset,
      logs: [],
      nextOffset: intOffset,
      atEnd: intOffset >= intSize,
      skipped: [],
    };
    if (batch.atEnd) return batch;
    const buffer = Buffer.alloc(INT_LOG_READ_BYTES);
    // The extra byte holds the CR in a CRLF line ending without reducing the allowed log size.
    const lineBuffer = Buffer.alloc(INT_LOG_ENTRY_BYTES + 1);
    const decoder = new TextDecoder("utf-8", { fatal: true });
    let intPosition = intOffset;
    let intLineBytes = 0;
    let intLastByte = 0;
    let intLines = 0;
    let intBatchBytes = Buffer.byteLength('{"logs":[],"complete":false}', "utf8");

    function finishLine(nextOffset: number): boolean {
      const intContentBytes = intLineBytes - (intLastByte === 13 ? 1 : 0);
      let strReason = "";
      let strLine = "";
      if (intContentBytes > INT_LOG_ENTRY_BYTES) {
        strReason = "The log entry exceeds 256 KiB.";
      } else {
        try {
          strLine = decoder.decode(lineBuffer.subarray(0, intContentBytes)).trim();
        } catch {
          strReason = "The log entry is not valid UTF-8.";
        }
      }
      if (strLine) {
        const intBytes =
          Buffer.byteLength(JSON.stringify(strLine), "utf8") + (batch.logs.length ? 1 : 0);
        if (intBatchBytes + intBytes > INT_LOG_BATCH_BYTES) return false;
        // Keep source JSON as text; parsing its numbers in JavaScript can lose precision.
        batch.logs.push(strLine);
        intBatchBytes += intBytes;
      }
      if (strReason) batch.skipped.push({ offset: batch.nextOffset, reason: strReason });
      batch.nextOffset = nextOffset;
      intLineBytes = 0;
      intLastByte = 0;
      intLines++;
      return intLines < INT_LOG_BATCH_ENTRIES;
    }

    let boolContinue = true;
    while (intPosition < intSize && boolContinue) {
      abortLogs.signal.throwIfAborted();
      const { bytesRead: intRead } = await fileObj.read(
        buffer,
        0,
        Math.min(buffer.length, intSize - intPosition),
        intPosition,
      );
      if (!intRead) break;
      let intStart = 0;
      while (intStart < intRead) {
        const intNewline = buffer.indexOf(10, intStart);
        const boolNewline = intNewline >= 0 && intNewline < intRead;
        const intEnd = boolNewline ? intNewline : intRead;
        const intPartBytes = intEnd - intStart;
        if (intPartBytes) {
          const intCopyBytes = Math.min(
            intPartBytes,
            Math.max(0, lineBuffer.length - intLineBytes),
          );
          if (intCopyBytes)
            buffer.copy(lineBuffer, intLineBytes, intStart, intStart + intCopyBytes);
          intLineBytes += intPartBytes;
          intLastByte = buffer[intEnd - 1];
        }
        if (boolNewline && !finishLine(intPosition + intEnd + 1)) {
          boolContinue = false;
          break;
        }
        intStart = intEnd + (boolNewline ? 1 : 0);
      }
      intPosition += intRead;
    }
    // A running process may still be writing its final line; wait for the line ending before reading it.
    if (boolContinue && ended && intPosition >= intSize && intLineBytes)
      finishLine(intSize);
    batch.atEnd = batch.nextOffset >= intSize;
    return batch;
  } finally {
    await fileObj.close();
  }
}

function getLogRejections(response: Record<string, unknown>, logs: string[]): string[] {
  if (response.accepted !== true)
    throw new Error("Console did not acknowledge the MachineLog batch.");
  if (response.accepting === false) return [];
  if (
    response.accepting !== true ||
    !Array.isArray(response.saved) ||
    !Array.isArray(response.existing) ||
    !Array.isArray(response.rejected)
  )
    throw new Error("Console returned an incomplete MachineLog acknowledgment.");
  const setAcknowledged = new Set(
    [...response.saved, ...response.existing].map((value) =>
      ensureNonEmptyString(value, "Acknowledged log ID").toLowerCase(),
    ),
  );
  const mapRejected = new Map<number, string>();
  for (const value of response.rejected) {
    const rejection = ensureRecord(value, "Rejected log entry");
    const intIndex = rejection.index;
    if (
      typeof intIndex !== "number" ||
      !Number.isInteger(intIndex) ||
      intIndex < 0 ||
      intIndex >= logs.length ||
      mapRejected.has(intIndex)
    )
      throw new Error("Console returned an invalid rejected log index.");
    mapRejected.set(intIndex, ensureNonEmptyString(rejection.reason, "Log rejection"));
  }
  for (const [intIndex, value] of logs.entries()) {
    if (mapRejected.has(intIndex)) continue;
    // Parse only to check the log ID; never replace the original JSON text with JSON.stringify output.
    const log = ensureRecord(JSON.parse(value) as unknown, "Acknowledged log entry");
    const strLogId = ensureNonEmptyString(log.logId, "Log ID").toLowerCase();
    if (!setAcknowledged.has(strLogId))
      throw new Error(`Console did not acknowledge MachineLog batch entry ${intIndex}.`);
  }
  return [...mapRejected].map(([intIndex, strReason]) => `${intIndex}: ${strReason}`);
}

async function uploadRunLogs(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  if (record.ended && record.assignment.snapshot.builtin_record_video === true) {
    const recording = record.recording;
    if (
      recording?.status !== RunRecordingStatus.Ready &&
      recording?.status !== RunRecordingStatus.Unavailable
    ) {
      const currentRecording = readRunRecording(
        record.ended.logPath,
        Date.parse(record.ended.endedAt),
      );
      if (currentRecording) reportConsoleRecording(record.assignment.id, currentRecording);
    }
  }
  if (!record.started || record.logsFinished) return;
  if (record.logsUnavailableReason !== undefined) {
    const response = await requestConsole(
      credential.consoleUrl,
      `executor/runs/${record.assignment.run_id}/logs/`,
      credential.token,
      { logs: [], complete: false, unavailable_reason: record.logsUnavailableReason },
    );
    getLogRejections(response, []);
    saveConsoleLogProgress(
      record.assignment.id,
      record.logOffsets,
      true,
      record.logsUnavailableReason,
    );
    return;
  }
  if (!fs.existsSync(record.started.logPath)) return;
  const strFolder = ensureExistingRunLogFolderPath(record.started.logPath);
  const arrName = fs
    .readdirSync(strFolder)
    .filter((strName) => /^machine_read_.+\.jsonl(?:\.\d+)?$/.test(strName))
    .sort();
  let boolAtEnd = true;
  for (const strName of arrName) {
    const strFilePath = path.join(strFolder, strName);
    const batch = await readLogBatch(
      strFilePath,
      record.logOffsets,
      record.ended !== undefined,
    );
    const { fileKey: strFileKey, startOffset: intOffset } = batch;
    boolAtEnd &&= batch.atEnd;
    let arrRejected: string[] = [];
    if (batch.logs.length) {
      const response = await requestConsole(
        credential.consoleUrl,
        `executor/runs/${record.assignment.run_id}/logs/`,
        credential.token,
        { logs: batch.logs, complete: false },
      );
      arrRejected = getLogRejections(response, batch.logs);
      if (response.accepting === false) {
        record.logsFinished = true;
        saveConsoleLogProgress(record.assignment.id, record.logOffsets, true);
        break;
      }
    }
    if (batch.nextOffset === intOffset) continue;
    // Advance the saved offset only past confirmed entries and whole lines rejected locally.
    record.logOffsets[strFileKey] = batch.nextOffset;
    saveConsoleLogProgress(record.assignment.id, record.logOffsets, record.logsFinished);
    if (arrRejected.length)
      loggerMain.warn(
        `Console rejected ${arrRejected.length} MachineLog entries for Run ` +
          `${record.assignment.run_id}, file ${strName}, batch at byte ${intOffset}. ` +
          `Rejected indexes: ${arrRejected.join("; ")}. ` +
          `Original logs remain in ${strFolder}.`,
      );
    if (batch.skipped.length) {
      const strDetails = batch.skipped
        .map((entry) => `byte ${entry.offset}: ${entry.reason}`)
        .join("; ");
      loggerMain.warn(
        `Skipped ${batch.skipped.length} MachineLog entries for Run ` +
          `${record.assignment.run_id}, file ${strName}: ${strDetails}. ` +
          `Original logs remain in ${strFolder}.`,
      );
    }
  }
  if (!record.logsFinished && record.ended && boolAtEnd) {
    // Log cleanup may have removed the source while the upload was waiting for a response.
    if (getConsoleWork(record.assignment.id)?.logsUnavailableReason !== undefined) return;
    const response = await requestConsole(
      credential.consoleUrl,
      `executor/runs/${record.assignment.run_id}/logs/`,
      credential.token,
      { logs: [], complete: true },
    );
    getLogRejections(response, []);
    record.logsFinished = true;
    saveConsoleLogProgress(record.assignment.id, record.logOffsets, true);
  }
}

export async function uploadConsoleLogs(
  sessionKey: string,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  if ((mapLogSessionRetryAt.get(sessionKey) ?? 0) > performance.now()) return;
  mapLogSessionRetryAt.delete(sessionKey);
  for (const record of getPendingConsoleLogWork(sessionKey)) {
    const retry = mapLogRetry.get(record.assignment.id);
    if (retry && retry.nextAt > performance.now()) continue;
    try {
      await uploadRunLogs(record, credential);
      mapLogRetry.delete(record.assignment.id);
    } catch (e: unknown) {
      if (!retry)
        loggerMain.warn(
          `Console logs for Run ${record.assignment.run_id}: ${getErrorMessage(e)}`,
        );
      const intDelayMs = Math.min((retry?.delayMs ?? 1000) * 2, 30_000);
      mapLogRetry.set(record.assignment.id, {
        nextAt: performance.now() + intDelayMs,
        delayMs: intDelayMs,
      });
      if (e instanceof ConsoleRequestError && (e.status === 429 || e.retryAfterMs > 0)) {
        // All Run log uploads share this client's request rate limit.
        mapLogSessionRetryAt.set(
          sessionKey,
          performance.now() + Math.max(intDelayMs, e.retryAfterMs),
        );
        break;
      }
    }
  }
}

