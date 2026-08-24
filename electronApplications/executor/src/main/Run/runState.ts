import type { ChildProcessWithoutNullStreams } from "child_process";
import fs from "fs";
import path from "path";

import { ensureNonEmptyString, ensureRecord, ensureString } from "../Common/validation";
import { strDocumentsFolderPath } from "../Config/environment";
import { loggerMain } from "../Logging/logger";
import { ensureExpectedRunLogFolderPath, ensureRunLogFolderPath } from "./logPath";
import { isPythonProcessRunning } from "./pythonProcess";

export type ExecutorRunStateStatus = "running" | "completed" | "error" | "terminated";

export interface ExecutorRunState {
  schemaVersion: 1;
  runId: string;
  packageName: string;
  packageVersion: string;
  startedAt: string;
  logPath: string;
  status: ExecutorRunStateStatus;
  endedAt?: string;
}

const INT_INITIAL_RUN_STATE_INTERVAL_MS = 250;
const INT_INITIAL_RUN_STATE_TIMEOUT_MS = 15 * 1000;
const REGEX_ISO_TIMESTAMP_WITH_TIMEZONE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;

const strExecutorRunStateFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA/ExecutorRunState",
);

export function createExecutorRunStatePath(strRunId: string): string {
  fs.mkdirSync(strExecutorRunStateFolderPath, { recursive: true });
  return path.join(strExecutorRunStateFolderPath, `${strRunId}.json`);
}

export function removeExecutorRunStateFile(strRunStatePath: string): void {
  try {
    fs.rmSync(strRunStatePath, { force: true });
  } catch (e: unknown) {
    loggerMain.warn(
      `Failed to remove Executor run-state file ${strRunStatePath}: ${getErrorMessage(e)}`,
    );
  }
}

function isValidExecutorRunTimestamp(value: string): boolean {
  if (!REGEX_ISO_TIMESTAMP_WITH_TIMEZONE.test(value)) {
    return false;
  }

  const intTimestampMs = Date.parse(value);
  return Number.isSafeInteger(intTimestampMs) && intTimestampMs >= 0;
}

export function parseExecutorRunTimestamp(strTimestamp: string): number {
  const intTimestampMs = Date.parse(strTimestamp);
  if (
    !REGEX_ISO_TIMESTAMP_WITH_TIMEZONE.test(strTimestamp) ||
    !Number.isSafeInteger(intTimestampMs) ||
    intTimestampMs < 0
  ) {
    throw new Error(`Invalid Executor run timestamp: ${strTimestamp}`);
  }
  return intTimestampMs;
}

function ensureExecutorRunStateStatus(value: unknown): ExecutorRunStateStatus {
  switch (value) {
    case "running":
    case "completed":
    case "error":
    case "terminated":
      return value;
    default:
      throw new Error("Executor run state contains an unsupported status.");
  }
}

export function readExecutorRunState({
  filePath,
  expectedRunId,
  expectedPackageName,
  expectedPackageVersion,
  expectedLogRootPath,
  expectedLogPath,
}: {
  filePath: string;
  expectedRunId: string;
  expectedPackageName: string;
  expectedPackageVersion: string;
  expectedLogRootPath: string;
  expectedLogPath?: string;
}): ExecutorRunState {
  const strContent = fs.readFileSync(filePath, { encoding: "utf-8" });
  const value: unknown = JSON.parse(strContent);
  const dictState = ensureRecord(value, "Executor run state");

  if (dictState.schemaVersion !== 1) {
    throw new Error(
      `Invalid Executor run state schema version: ${String(dictState.schemaVersion)}`,
    );
  }
  if (dictState.runId !== expectedRunId) {
    throw new Error(`Executor run state has an unexpected runId: ${filePath}`);
  }
  if (dictState.packageName !== expectedPackageName) {
    throw new Error(`Executor run state has an unexpected packageName: ${filePath}`);
  }
  if (dictState.packageVersion !== expectedPackageVersion) {
    throw new Error(`Executor run state has an unexpected packageVersion: ${filePath}`);
  }

  const strStartedAt = ensureString(dictState.startedAt, "Executor run state.startedAt");
  if (!isValidExecutorRunTimestamp(strStartedAt)) {
    throw new Error(`Invalid Executor run state startedAt: ${strStartedAt}`);
  }
  const strRawLogPath = ensureNonEmptyString(
    dictState.logPath,
    "Executor run state.logPath",
  );
  const strLogPath =
    expectedLogPath === undefined
      ? ensureRunLogFolderPath(strRawLogPath, expectedLogRootPath)
      : ensureExpectedRunLogFolderPath(strRawLogPath, expectedLogPath);
  const status = ensureExecutorRunStateStatus(dictState.status);

  if (status === "running") {
    if (dictState.endedAt !== undefined) {
      throw new Error("A running Executor run state cannot contain endedAt.");
    }
    return {
      schemaVersion: 1,
      runId: expectedRunId,
      packageName: expectedPackageName,
      packageVersion: expectedPackageVersion,
      startedAt: strStartedAt,
      logPath: strLogPath,
      status,
    };
  }

  const strEndedAt = ensureString(dictState.endedAt, "Executor run state.endedAt");
  if (!isValidExecutorRunTimestamp(strEndedAt)) {
    throw new Error(`Invalid Executor run state endedAt: ${strEndedAt}`);
  }
  return {
    schemaVersion: 1,
    runId: expectedRunId,
    packageName: expectedPackageName,
    packageVersion: expectedPackageVersion,
    startedAt: strStartedAt,
    logPath: strLogPath,
    status,
    endedAt: strEndedAt,
  };
}

export async function waitForExecutorRunStateAvailable({
  filePath,
  processPy,
  getProcessError,
  expectedRunId,
  expectedPackageName,
  expectedPackageVersion,
  expectedLogRootPath,
}: {
  filePath: string;
  processPy: ChildProcessWithoutNullStreams;
  getProcessError: () => Error | undefined;
  expectedRunId: string;
  expectedPackageName: string;
  expectedPackageVersion: string;
  expectedLogRootPath: string;
}): Promise<ExecutorRunState> {
  let intElapsedMs = 0;

  while (intElapsedMs < INT_INITIAL_RUN_STATE_TIMEOUT_MS) {
    const processError = getProcessError();
    if (processError !== undefined) {
      throw new Error(`Python process failed to start: ${processError.message}`, {
        cause: processError,
      });
    }

    if (fs.existsSync(filePath)) {
      return readExecutorRunState({
        filePath,
        expectedRunId,
        expectedPackageName,
        expectedPackageVersion,
        expectedLogRootPath,
      });
    }

    if (!isPythonProcessRunning(processPy)) {
      throw new Error(
        `Python exited before publishing the initial Executor run state: ${expectedRunId}`,
      );
    }

    await new Promise<void>((resolve) => {
      setTimeout(resolve, INT_INITIAL_RUN_STATE_INTERVAL_MS);
    });
    intElapsedMs += INT_INITIAL_RUN_STATE_INTERVAL_MS;
  }

  throw new Error(`Timeout waiting for the initial Executor run state: ${expectedRunId}`);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}
