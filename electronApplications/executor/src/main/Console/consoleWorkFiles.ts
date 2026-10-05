// FileName: consoleWorkFiles.ts

import fs from "fs";
import os from "os";
import path from "path";
import AdmZip from "adm-zip";

import { getErrorMessage } from "../../shared/error";
import { ensureNonEmptyString, ensureRecord } from "../Common/validation";
import { loggerMain } from "../Logging/logger";
import { ensureExistingRunLogFolderPath } from "../Run/logPath";
import { requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  getConsoleWorkRecords,
  saveConsoleLogProgress,
  reportConsoleRecording,
  type ConsoleWorkRecord,
} from "./workRepository";

const abortFiles = new AbortController();

export function stopConsoleFiles(): void {
  abortFiles.abort();
}

// Read two entry budgets at once; Console validates each entry against 256 KiB.
const INT_LOG_READ_BYTES = 512 * 1024;
const setTransferStarted = new Set<string>();
const mapLogRetry = new Map<string, { nextAt: number; delayMs: number }>();

function readLogBatch(
  filePath: string,
  offset: number,
): { logs: unknown[]; nextOffset: number; atEnd: boolean } {
  const intSize = fs.statSync(filePath).size;
  if (offset >= intSize) return { logs: [], nextOffset: offset, atEnd: true };
  const intFile = fs.openSync(filePath, "r");
  const buffer = Buffer.alloc(Math.min(INT_LOG_READ_BYTES, intSize - offset));
  let intRead: number;
  try {
    intRead = fs.readSync(intFile, buffer, 0, buffer.length, offset);
  } finally {
    fs.closeSync(intFile);
  }
  const arrLog: unknown[] = [];
  let intStart = 0;
  let intNextOffset = offset;
  for (let intIndex = 0; intIndex < intRead && arrLog.length < 500; intIndex++) {
    if (buffer[intIndex] !== 10) continue;
    const strLine = buffer.subarray(intStart, intIndex).toString("utf8").trim();
    if (strLine) arrLog.push(JSON.parse(strLine) as unknown);
    intStart = intIndex + 1;
    intNextOffset = offset + intStart;
  }
  if (intNextOffset === offset && intRead === INT_LOG_READ_BYTES)
    throw new Error(
      "A MachineLog line exceeds the 512 KiB read window; upload for this Run cannot continue. The original log file is retained.",
    );
  return { logs: arrLog, nextOffset: intNextOffset, atEnd: intNextOffset >= intSize };
}

function getLogRejections(response: Record<string, unknown>, logs: unknown[]): string[] {
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
    const log = ensureRecord(value, "Acknowledged log entry");
    const strLogId = ensureNonEmptyString(log.logId, "Log ID").toLowerCase();
    if (!setAcknowledged.has(strLogId))
      throw new Error(`Console did not acknowledge MachineLog batch entry ${intIndex}.`);
  }
  return [...mapRejected].map(([intIndex, strReason]) => `${intIndex}: ${strReason}`);
}

async function flushRunLogs(
  record: ConsoleWorkRecord,
  credential: ConsoleCredentialSnapshot,
): Promise<void> {
  if (
    record.ended &&
    record.assignment.snapshot.builtin_record_video === true &&
    !record.recordingReported?.includes('"status":"ready"') &&
    !record.recordingReported?.includes('"status":"unavailable"')
  ) {
    const strMarkerPath = path.join(record.ended.logPath, "video_record.state.json");
    if (fs.existsSync(strMarkerPath))
      reportConsoleRecording(
        record.assignment.id,
        ensureRecord(
          JSON.parse(fs.readFileSync(strMarkerPath, "utf8")) as unknown,
          "Recording state",
        ),
      );
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
    const stat = fs.statSync(strFilePath);
    const strFileKey = `${stat.dev}:${stat.ino}:${stat.birthtimeMs}`;
    const intStoredOffset = record.logOffsets[strFileKey] ?? 0;
    const intOffset = intStoredOffset > stat.size ? 0 : intStoredOffset;
    const batch = readLogBatch(strFilePath, intOffset);
    boolAtEnd &&= batch.atEnd;
    if (!batch.logs.length) continue;
    const response = await requestConsole(
      credential.consoleUrl,
      `executor/runs/${record.assignment.run_id}/logs/`,
      credential.token,
      { logs: batch.logs, complete: false },
    );
    const arrRejected = getLogRejections(response, batch.logs);
    if (response.accepting === false) {
      record.logsComplete = true;
      saveConsoleLogProgress(record.assignment.id, record.logOffsets, true);
      break;
    }
    if (arrRejected.length)
      loggerMain.warn(
        `Console rejected ${arrRejected.length} MachineLog entries for Run ${record.assignment.run_id}, file ${strName}, batch starting at byte ${intOffset}. Rejected indexes: ${arrRejected.join("; ")}. Original logs remain in ${strFolder}.`,
      );
    // Permanent rejections are reported once; retrying them would block later entries.
    record.logOffsets[strFileKey] = batch.nextOffset;
    saveConsoleLogProgress(record.assignment.id, record.logOffsets, record.logsComplete);
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
  for (const record of getConsoleWorkRecords(sessionKey)) {
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

function getTransferFile(
  record: ConsoleWorkRecord,
  kind: string,
): { filePath: string; temporaryFolder?: string; contentType: string; maxBytes: number } {
  if (!record.started || !record.ended)
    throw new Error("This actual Run has not ended on the original client.");
  const strFolder = ensureExistingRunLogFolderPath(record.started.logPath);
  const boolVideo = record.assignment.snapshot.builtin_record_video === true;
  if (boolVideo) {
    const strMarker = path.join(strFolder, "video_record.state.json");
    if (
      !fs.existsSync(strMarker) ||
      ensureRecord(
        JSON.parse(fs.readFileSync(strMarker, "utf8")) as unknown,
        "Recording state",
      ).status !== "ready"
    )
      throw new Error("Recording finalization has not completed successfully.");
  }
  if (kind === "logs") {
    const arrName = fs
      .readdirSync(strFolder)
      .filter((strName) => /^human_read_.+\.log(?:\.\d+)?$/.test(strName));
    if (!arrName.length)
      throw new Error("The original HumanReadableLog files are unavailable.");
    const strTemporaryFolder = fs.mkdtempSync(path.join(os.tmpdir(), "liberrpa-logs-"));
    const strFilePath = path.join(
      strTemporaryFolder,
      `${record.assignment.run_id}-logs.zip`,
    );
    const zipObj = new AdmZip();
    for (const strName of arrName) zipObj.addLocalFile(path.join(strFolder, strName));
    zipObj.writeZip(strFilePath);
    return {
      filePath: strFilePath,
      temporaryFolder: strTemporaryFolder,
      contentType: "application/zip",
      maxBytes: 2 * 1024 ** 3,
    };
  }
  if (kind === "video")
    return {
      filePath: path.join(strFolder, "video_record.mkv"),
      contentType: "video/x-matroska",
      maxBytes: 512 * 1024 ** 2,
    };
  if (kind === "subtitles")
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
    const record = getConsoleWorkRecords(sessionKey).find(
      (record) => record.assignment.run_id === transfer.run_id,
    );
    if (!record) throw new Error("The original Run is unavailable on this client.");
    const source = getTransferFile(
      record,
      ensureNonEmptyString(transfer.kind, "File kind"),
    );
    strTemporaryFolder = source.temporaryFolder;
    const stat = fs.statSync(source.filePath);
    if (!stat.isFile() || stat.size > source.maxBytes)
      throw new Error(
        "The requested original file is missing or exceeds its download limit.",
      );
    await requestConsole(
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
    const response = await fetch(
      `${credential.consoleUrl}/api/clients/executor/file-transfers/${encodeURIComponent(strTransferId)}/content/`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${credential.token}`,
          "Content-Type": source.contentType,
          "Content-Length": String(stat.size),
        },
        body: fs.createReadStream(source.filePath) as unknown as BodyInit,
        duplex: "half",
        redirect: "error",
        credentials: "omit",
        signal: AbortSignal.any([AbortSignal.timeout(120_000), abortFiles.signal]),
      } as RequestInit,
    );
    if (!response.ok)
      throw new Error(`Original file transfer failed (${response.status}).`);
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
    if (strTemporaryFolder) fs.rmSync(strTemporaryFolder, { recursive: true, force: true });
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
