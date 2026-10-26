// FileName: consoleFileTransfers.ts

import fs from "fs";
import http, { type IncomingMessage } from "http";
import https from "https";
import { performance } from "perf_hooks";
import { finished } from "stream/promises";
import path from "path";

import { RunRecordingStatus } from "../../shared/run";
import { getErrorMessage } from "../../shared/error";
import {
  ensureRecord,
  ensureNonEmptyString,
  ensurePositiveInteger,
} from "../Common/validation";
import { strDocumentsFolderPath } from "../Config/environment";
import { runFileWorker } from "../FileSystem/fileWorker";
import { loggerMain } from "../Logging/logger";
import { ensureExistingRunLogFolderPath } from "../Run/logPath";
import { readRunRecording } from "../Run/recording";
import { requestConsole } from "./consoleApi";
import strLogArchiveWorkerPath from "./logArchiveWorker?modulePath";
import type { LogArchiveArgs } from "./logArchiveWorker";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import { type ConsoleWorkRecord, getConsoleWorkForRun } from "./workRepository";

const strLogArchiveFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA/AppData/executor/log-archives",
);
const abortTransfers = new AbortController();

export function stopConsoleFileTransfers(): void {
  abortTransfers.abort();
}

enum ConsoleRunFileKind {
  Logs = "logs",
  Video = "video",
  Subtitles = "subtitles",
}

const setTransferStarted = new Set<string>();

export async function cleanConsoleLogArchives(): Promise<void> {
  try {
    if (!(await fs.promises.lstat(strLogArchiveFolderPath)).isDirectory()) return;
    const arrEntry = await fs.promises.readdir(strLogArchiveFolderPath, {
      withFileTypes: true,
    });
    let intRemoved = 0;
    // Only this Executor's generated temporary folders; never scan the system Temp root.
    for (const entry of arrEntry) {
      if (!entry.isDirectory() || !/^archive-[A-Za-z0-9]{6}$/.test(entry.name)) continue;
      const strArchivePath = path.join(strLogArchiveFolderPath, entry.name);
      try {
        await fs.promises.rm(strArchivePath, { recursive: true, force: true });
        intRemoved += 1;
      } catch (e: unknown) {
        loggerMain.warn(
          `Failed to remove temporary log archive ${strArchivePath}: ${getErrorMessage(e)}`,
        );
      }
    }
    if (intRemoved)
      loggerMain.info(`Removed ${intRemoved} abandoned Console log archive folders.`);
  } catch (e: unknown) {
    if (!(e instanceof Error && "code" in e && e.code === "ENOENT"))
      loggerMain.warn(`Failed to inspect Console log archives: ${getErrorMessage(e)}`);
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
  abortTransfers.signal.throwIfAborted();
  const strExitConfirmedAt = record.ended?.endedAt ?? record.interruptedAt;
  if (!record.started || strExitConfirmedAt === undefined)
    throw new Error("The original Python process has not been confirmed to have exited.");
  const strFolder = ensureExistingRunLogFolderPath(record.started.logPath);
  const boolVideo = record.assignment.snapshot.builtin_record_video === true;
  const recordingStatus = boolVideo
    ? readRunRecording(strFolder, Date.parse(strExitConfirmedAt))?.status
    : undefined;
  if (
    boolVideo &&
    recordingStatus !== RunRecordingStatus.Ready &&
    recordingStatus !== RunRecordingStatus.Unavailable
  )
    throw new Error("Wait until the recording has finished.");
  if (kind !== ConsoleRunFileKind.Logs && recordingStatus !== RunRecordingStatus.Ready)
    throw new Error("This Run has no completed recording available.");
  if (kind === ConsoleRunFileKind.Logs) {
    await fs.promises.mkdir(strLogArchiveFolderPath, { recursive: true });
    const strTemporaryFolder = await fs.promises.mkdtemp(
      path.join(strLogArchiveFolderPath, "archive-"),
    );
    const strFilePath = path.join(
      strTemporaryFolder,
      `${record.assignment.run_id}-logs.zip`,
    );
    try {
      await runFileWorker<LogArchiveArgs>(
        strLogArchiveWorkerPath,
        { logFolderPath: strFolder, archiveFilePath: strFilePath },
        abortTransfers.signal,
      );
    } catch (e: unknown) {
      await fs.promises.rm(strTemporaryFolder, { recursive: true, force: true });
      throw e;
    }
    return {
      filePath: strFilePath,
      temporaryFolder: strTemporaryFolder,
      contentType: "application/zip",
      maxBytes: 2 * 1024 ** 3, // 2 GiB
    };
  }
  if (kind === ConsoleRunFileKind.Video)
    return {
      filePath: path.join(strFolder, "video_record.mkv"),
      contentType: "video/x-matroska",
      maxBytes: 512 * 1024 ** 2, // 512 MiB
    };
  if (kind === ConsoleRunFileKind.Subtitles)
    return {
      filePath: path.join(strFolder, "video_record.srt"),
      contentType: "application/x-subrip",
      maxBytes: 10 * 1024 ** 2, // 10 MiB
    };
  throw new Error("Unsupported Run file kind.");
}

export async function sendConsoleFile(
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
    abortTransfers.signal.throwIfAborted();
    const floatReadyStartedAt = performance.now();
    const ready = await requestConsole(
      credential.consoleUrl,
      `executor/file-transfers/${encodeURIComponent(strTransferId)}/ready/`,
      credential.token,
      {
        size_bytes: stat.size,
        filename: path.basename(source.filePath),
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
    // Count the entire ready request against the timeout; do not compare clocks on different machines.
    const floatRemainingMs = intTimeoutMs - (performance.now() - floatReadyStartedAt);
    if (floatRemainingMs <= 0) throw new Error("The original file transfer has expired.");
    abortTransfers.signal.throwIfAborted();
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
      signal: abortTransfers.signal,
    });
    const fileStream = fs.createReadStream(source.filePath);
    let responseObj: IncomingMessage | undefined;
    const timerTotal = setTimeout(
      () => requestObj.destroy(new Error("The original file transfer has expired.")),
      floatRemainingMs,
    );
    // The socket idle timeout starts after connection; use a separate timer for DNS, TCP and TLS setup.
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
    // After upload, Console checks progress while the browser finishes reading the file.
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
        // Pipe pauses file reads when the network cannot keep up, so the whole file is not loaded into memory.
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
      try {
        await requestConsole(
          credential.consoleUrl,
          `executor/file-transfers/${encodeURIComponent(strTransferId)}/ready/`,
          credential.token,
          {
            size_bytes: 0,
            filename: "",
            error: getErrorMessage(e),
          },
        );
      } catch (e: unknown) {
        // Allow a later retry only after this preparation failure report has failed.
        setTransferStarted.delete(strTransferId);
        throw e;
      }
    } else throw e;
  } finally {
    if (strTemporaryFolder)
      await fs.promises.rm(strTemporaryFolder, { recursive: true, force: true });
  }
}
