// FileName: consoleWorkFiles.ts

import fs from "fs";
import http, { type IncomingMessage } from "http";
import https from "https";
import { performance } from "perf_hooks";
import { finished } from "stream/promises";
import os from "os";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import {
  ensureNonEmptyString,
  ensurePositiveInteger,
  ensureRecord,
  ensureNullableNonNegativeInteger,
  ensureString,
} from "../Common/validation";
import { runFileWorker } from "../FileSystem/fileWorker";
import { loggerMain } from "../Logging/logger";
import { ensureExistingRunLogFolderPath } from "../Run/logPath";
import { requestConsole } from "./consoleApi";
import strLogArchiveWorkerPath from "./logArchiveWorker?modulePath";
import type { LogArchiveArgs } from "./logArchiveWorker";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  ConsoleRecordingStatus,
  getConsoleWorkForRun,
  getPendingConsoleLogWork,
  saveConsoleLogProgress,
  reportConsoleRecording,
  type ConsoleWorkRecord,
  type ConsoleRecordingInfo,
} from "./workRepository";

const abortFiles = new AbortController();

export function stopConsoleFiles(): void {
  abortFiles.abort();
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

enum ConsoleRunFileKind {
  Logs = "logs",
  Video = "video",
  Subtitles = "subtitles",
}

const setTransferStarted = new Set<string>();
const mapLogRetry = new Map<string, { nextAt: number; delayMs: number }>();

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
    // One extra byte allows a CRLF terminator without reducing the entry budget.
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
      abortFiles.signal.throwIfAborted();
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
    // A running process may still be writing its final line; do not consume that tail.
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
    // Inspect only the acknowledged identity; never reserialize this parsed entry.
    const log = ensureRecord(JSON.parse(value) as unknown, "Acknowledged log entry");
    const strLogId = ensureNonEmptyString(log.logId, "Log ID").toLowerCase();
    if (!setAcknowledged.has(strLogId))
      throw new Error(`Console did not acknowledge MachineLog batch entry ${intIndex}.`);
  }
  return [...mapRejected].map(([intIndex, strReason]) => `${intIndex}: ${strReason}`);
}

function readConsoleRecording(filePath: string): ConsoleRecordingInfo {
  const dictRecording = ensureRecord(
    JSON.parse(fs.readFileSync(filePath, "utf8")) as unknown,
    "Recording state",
  );
  if (
    Object.keys(dictRecording).some(
      (strKey) =>
        !["status", "videoSizeBytes", "subtitleSizeBytes", "reason"].includes(strKey),
    )
  )
    throw new Error("Recording state contains unsupported fields.");
  const status = dictRecording.status;
  if (
    status !== ConsoleRecordingStatus.Recording &&
    status !== ConsoleRecordingStatus.Processing &&
    status !== ConsoleRecordingStatus.Ready &&
    status !== ConsoleRecordingStatus.Unavailable
  )
    throw new Error("Recording state contains an unsupported status.");
  const strReason = ensureString(
    dictRecording.reason === undefined ? "" : dictRecording.reason,
    "Recording reason",
  );
  if ([...strReason].length > 2000)
    throw new Error("Recording reason cannot exceed 2000 characters.");
  return {
    status,
    videoSizeBytes: ensureNullableNonNegativeInteger(
      dictRecording.videoSizeBytes ?? null,
      "Recording video size",
    ),
    subtitleSizeBytes: ensureNullableNonNegativeInteger(
      dictRecording.subtitleSizeBytes ?? null,
      "Recording subtitle size",
    ),
    reason: strReason,
  };
}

async function flushRunLogs(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  if (record.ended && record.assignment.snapshot.builtin_record_video === true) {
    const recording = record.recording;
    if (
      recording?.status !== ConsoleRecordingStatus.Ready &&
      recording?.status !== ConsoleRecordingStatus.Unavailable
    ) {
      const strMarkerPath = path.join(record.ended.logPath, "video_record.state.json");
      if (fs.existsSync(strMarkerPath))
        reportConsoleRecording(record.assignment.id, readConsoleRecording(strMarkerPath));
    }
  }
  if (!record.started || record.logsComplete || !fs.existsSync(record.started.logPath))
    return;
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
        record.logsComplete = true;
        saveConsoleLogProgress(record.assignment.id, record.logOffsets, true);
        break;
      }
    }
    if (batch.nextOffset === intOffset) continue;
    // Only acknowledged entries and locally rejected whole lines advance the saved cursor.
    record.logOffsets[strFileKey] = batch.nextOffset;
    saveConsoleLogProgress(record.assignment.id, record.logOffsets, record.logsComplete);
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
  if (!record.logsComplete && record.ended && boolAtEnd) {
    const response = await requestConsole(
      credential.consoleUrl,
      `executor/runs/${record.assignment.run_id}/logs/`,
      credential.token,
      { logs: [], complete: true },
    );
    getLogRejections(response, []);
    record.logsComplete = true;
    saveConsoleLogProgress(record.assignment.id, record.logOffsets, true);
  }
}

export async function flushConsoleLogs(
  sessionKey: string,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  for (const record of getPendingConsoleLogWork(sessionKey)) {
    const retry = mapLogRetry.get(record.assignment.id);
    if (retry && retry.nextAt > Date.now()) continue;
    try {
      await flushRunLogs(record, credential);
      mapLogRetry.delete(record.assignment.id);
    } catch (e: unknown) {
      if (!retry)
        loggerMain.warn(
          `Console logs for Run ${record.assignment.run_id}: ${getErrorMessage(e)}`,
        );
      const intDelayMs = Math.min((retry?.delayMs ?? 1000) * 2, 30_000);
      mapLogRetry.set(record.assignment.id, {
        nextAt: Date.now() + intDelayMs,
        delayMs: intDelayMs,
      });
    }
  }
}

async function prepareTransferFile(
  record: ConsoleWorkRecord,
  kind: ConsoleRunFileKind,
): Promise<{
  filePath: string;
  temporaryFolder?: string;
  contentType: string;
  maxBytes: number;
}> {
  abortFiles.signal.throwIfAborted();
  if (!record.started || !record.ended)
    throw new Error("This actual Run has not ended on the original client.");
  const strFolder = ensureExistingRunLogFolderPath(record.started.logPath);
  const boolVideo = record.assignment.snapshot.builtin_record_video === true;
  if (boolVideo) {
    const strMarker = path.join(strFolder, "video_record.state.json");
    if (
      !fs.existsSync(strMarker) ||
      readConsoleRecording(strMarker).status !== ConsoleRecordingStatus.Ready
    )
      throw new Error("Recording finalization has not completed successfully.");
  }
  if (kind === ConsoleRunFileKind.Logs) {
    const strTemporaryFolder = await fs.promises.mkdtemp(
      path.join(os.tmpdir(), "liberrpa-logs-"),
    );
    const strFilePath = path.join(
      strTemporaryFolder,
      `${record.assignment.run_id}-logs.zip`,
    );
    try {
      await runFileWorker<LogArchiveArgs>(
        strLogArchiveWorkerPath,
        { logFolderPath: strFolder, archiveFilePath: strFilePath },
        abortFiles.signal,
      );
    } catch (e: unknown) {
      await fs.promises.rm(strTemporaryFolder, { recursive: true, force: true });
      throw e;
    }
    return {
      filePath: strFilePath,
      temporaryFolder: strTemporaryFolder,
      contentType: "application/zip",
      maxBytes: 2 * 1024 ** 3,
    };
  }
  if (kind === ConsoleRunFileKind.Video)
    return {
      filePath: path.join(strFolder, "video_record.mkv"),
      contentType: "video/x-matroska",
      maxBytes: 512 * 1024 ** 2,
    };
  if (kind === ConsoleRunFileKind.Subtitles)
    return {
      filePath: path.join(strFolder, "video_record.srt"),
      contentType: "application/x-subrip",
      maxBytes: 10 * 1024 ** 2,
    };
  throw new Error("Unsupported Run file kind.");
}

async function sendConsoleFile(
  sessionKey: string,
  credential: ConsoleCredentialSnapshot,
  value: unknown,
): Promise<void> {
  const transfer = ensureRecord(value, "Run file transfer");
  const strTransferId = ensureNonEmptyString(transfer.id, "Transfer ID");
  if (setTransferStarted.has(strTransferId)) return;
  setTransferStarted.add(strTransferId);
  let strTemporaryFolder: string | undefined;
  let boolReady = false;
  try {
    const strKind = ensureNonEmptyString(transfer.kind, "File kind");
    const fileKind = Object.values(ConsoleRunFileKind).find((kind) => kind === strKind);
    if (fileKind === undefined) throw new Error("Unsupported Run file kind.");
    const record = getConsoleWorkForRun(
      sessionKey,
      ensureNonEmptyString(transfer.run_id, "Transfer Run ID"),
    );
    if (!record) throw new Error("The original Run is unavailable on this client.");
    const source = await prepareTransferFile(record, fileKind);
    strTemporaryFolder = source.temporaryFolder;
    const stat = await fs.promises.stat(source.filePath);
    if (!stat.isFile() || stat.size > source.maxBytes)
      throw new Error(
        "The requested original file is missing or exceeds its download limit.",
      );
    abortFiles.signal.throwIfAborted();
    const floatReadyStartedAt = performance.now();
    const ready = await requestConsole(
      credential.consoleUrl,
      `executor/file-transfers/${encodeURIComponent(strTransferId)}/ready/`,
      credential.token,
      {
        size_bytes: stat.size,
        filename: path.basename(source.filePath),
        content_type: source.contentType,
      },
    );
    boolReady = true;
    if (ready.ready !== true)
      throw new Error("Console did not accept the prepared original file.");
    const intTimeoutMs = ensurePositiveInteger(
      ready.transfer_timeout_ms,
      "File transfer timeout",
    );
    const intIdleMs = ensurePositiveInteger(ready.idle_timeout_ms, "File idle timeout");
    if (intTimeoutMs > 2_147_483_647 || intIdleMs > 2_147_483_647)
      throw new Error("Console returned an unsupported file transfer timeout.");
    // Conservatively include the complete ready request without comparing wall clocks.
    const floatRemainingMs = intTimeoutMs - (performance.now() - floatReadyStartedAt);
    if (floatRemainingMs <= 0) throw new Error("The original file transfer has expired.");
    abortFiles.signal.throwIfAborted();
    const urlObj = new URL(
      `${credential.consoleUrl}/api/clients/executor/file-transfers/${encodeURIComponent(strTransferId)}/content/`,
    );
    const requestUpload = urlObj.protocol === "https:" ? https.request : http.request;
    const requestObj = requestUpload(urlObj, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${credential.token}`,
        "Content-Type": source.contentType,
        "Content-Length": String(stat.size),
      },
      agent: false,
      signal: abortFiles.signal,
    });
    const fileStream = fs.createReadStream(source.filePath);
    let responseObj: IncomingMessage | undefined;
    const timerTotal = setTimeout(
      () => requestObj.destroy(new Error("The original file transfer has expired.")),
      floatRemainingMs,
    );
    // Socket inactivity starts after connection; also bound DNS, TCP and TLS setup.
    const timerConnect = setTimeout(
      () => requestObj.destroy(new Error("The file transfer connection timed out.")),
      intIdleMs,
    );
    requestObj.once("socket", (socket) => {
      socket.once(urlObj.protocol === "https:" ? "secureConnect" : "connect", () =>
        clearTimeout(timerConnect),
      );
    });
    requestObj.setTimeout(intIdleMs, () =>
      requestObj.destroy(new Error("The original file transfer stopped making progress.")),
    );
    // Once sent, the relay owns progress checks while its browser consumer drains buffers.
    requestObj.once("finish", () => {
      if (!responseObj) requestObj.setTimeout(0);
    });
    try {
      await new Promise<void>((resolve, reject) => {
        requestObj.once("error", reject);
        fileStream.once("error", reject);
        requestObj.once("response", (response) => {
          responseObj = response;
          requestObj.setTimeout(intIdleMs);
          response.once("error", reject);
          if (response.statusCode !== 200) {
            reject(new Error(`Original file transfer failed (${response.statusCode}).`));
            return;
          }
          let intBytes = 0;
          const arrChunk: Buffer[] = [];
          response.on("data", (chunk: Buffer) => {
            intBytes += chunk.length;
            if (intBytes > 1024) {
              reject(new Error("Console returned an oversized file acknowledgment."));
              return;
            }
            arrChunk.push(chunk);
          });
          response.once("end", () => {
            try {
              const acknowledgment = ensureRecord(
                JSON.parse(Buffer.concat(arrChunk).toString("utf8")) as unknown,
                "File acknowledgment",
              );
              if (acknowledgment.received !== true)
                throw new Error("Console did not acknowledge the original file.");
              resolve();
            } catch (e: unknown) {
              reject(e);
            }
          });
        });
        // Pipe preserves backpressure; only this long request uses a streaming transport.
        fileStream.pipe(requestObj);
      });
    } finally {
      clearTimeout(timerTotal);
      clearTimeout(timerConnect);
      responseObj?.destroy();
      requestObj.destroy();
      fileStream.destroy();
      // Windows cannot remove a temporary ZIP until its reader has closed.
      await finished(fileStream, { cleanup: true }).catch(() => {});
    }
  } catch (e: unknown) {
    if (!boolReady) {
      setTransferStarted.delete(strTransferId);
      await requestConsole(
        credential.consoleUrl,
        `executor/file-transfers/${encodeURIComponent(strTransferId)}/ready/`,
        credential.token,
        {
          size_bytes: 0,
          filename: "",
          content_type: "application/octet-stream",
          error: getErrorMessage(e),
        },
      );
      setTransferStarted.add(strTransferId);
    } else throw e;
  } finally {
    if (strTemporaryFolder)
      await fs.promises.rm(strTemporaryFolder, { recursive: true, force: true });
  }
}

export async function sendConsoleFiles(
  sessionKey: string,
  credential: ConsoleCredentialSnapshot,
  value: unknown,
): Promise<void> {
  if (!Array.isArray(value)) return;
  for (const transfer of value) await sendConsoleFile(sessionKey, credential, transfer);
}
