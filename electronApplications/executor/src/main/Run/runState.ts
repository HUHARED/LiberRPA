// FileName: runState.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { isProcessRunning } from "../Common/process";
import {
  ensureExactRecord,
  ensureNonEmptyString,
  ensureRecord,
  ensureString,
} from "../Common/validation";
import { strDocumentsFolderPath } from "../Config/environment";
import { loggerMain } from "../Logging/logger";
import { ensureExpectedRunLogFolderPath, ensureRunLogFolderPath } from "./logPath";

type Str_ExecutorRunState_Status = "running" | "completed" | "error" | "terminated";

export interface ExecutorRunState {
  schemaVersion: 1;
  runId: string;
  packageName: string;
  packageVersion: string;
  startedAt: string;
  logPath: string;
  status: Str_ExecutorRunState_Status;
  endedAt?: string;
}

const INT_INITIAL_RUN_STATE_INTERVAL_MS = 250;
const INT_INITIAL_RUN_STATE_TIMEOUT_MS = 15 * 1000;
const REGEX_ISO_TIMESTAMP_WITH_TIMEZONE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
const ARR_RUNNING_RUN_STATE_KEY = [
  "schemaVersion",
  "runId",
  "packageName",
  "packageVersion",
  "startedAt",
  "logPath",
  "status",
] as const;
const ARR_FINAL_RUN_STATE_KEY = [...ARR_RUNNING_RUN_STATE_KEY, "endedAt"] as const;

const strExecutorRunStateFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA/ExecutorRunState",
);

export function createExecutorRunStatePath(runId: string): string {
  fs.mkdirSync(strExecutorRunStateFolderPath, { recursive: true });
  return path.join(strExecutorRunStateFolderPath, `${runId}.json`);
}

export function removeExecutorRunStateFile(runStatePath: string): void {
  try {
    fs.rmSync(runStatePath, { force: true });
  } catch (e: unknown) {
    loggerMain.warn(
      `Failed to remove Executor run-state file ${runStatePath}: ${getErrorMessage(e)}`,
    );
  }
}

export function parseExecutorRunTimestamp(timestamp: string): number {
  const intTimestampMs = Date.parse(timestamp);
  if (
    !REGEX_ISO_TIMESTAMP_WITH_TIMEZONE.test(timestamp) ||
    !Number.isSafeInteger(intTimestampMs) ||
    intTimestampMs < 0
  ) {
    throw new Error(`Invalid Executor run timestamp: ${timestamp}`);
  }
  return intTimestampMs;
}

function ensureExecutorRunStateStatus(value: unknown): Str_ExecutorRunState_Status {
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
  expectedStartedAt,
  expectedLogRootPath,
  expectedLogPath,
}: {
  filePath: string;
  expectedRunId: string;
  expectedPackageName: string;
  expectedPackageVersion: string;
  expectedStartedAt: string;
  expectedLogRootPath: string;
  expectedLogPath?: string;
}): ExecutorRunState {
  const strContent = fs.readFileSync(filePath, { encoding: "utf-8" });
  const value: unknown = JSON.parse(strContent);
  const dictRawState = ensureRecord(value, "Executor run state");
  const status = ensureExecutorRunStateStatus(dictRawState.status);
  const dictState = ensureExactRecord(
    value,
    status === "running" ? ARR_RUNNING_RUN_STATE_KEY : ARR_FINAL_RUN_STATE_KEY,
    "Executor run state",
  );

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
  const intStartedAtMs = parseExecutorRunTimestamp(strStartedAt);
  const intExpectedStartedAtMs = parseExecutorRunTimestamp(expectedStartedAt);
  if (intStartedAtMs !== intExpectedStartedAtMs) {
    throw new Error(`Executor run state has an unexpected startedAt: ${filePath}`);
  }

  const strRawLogPath = ensureNonEmptyString(
    dictState.logPath,
    "Executor run state.logPath",
  );
  const strLogPath =
    expectedLogPath === undefined
      ? ensureRunLogFolderPath(strRawLogPath, expectedLogRootPath)
      : ensureExpectedRunLogFolderPath(strRawLogPath, expectedLogPath);

  if (status === "running") {
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
  const intEndedAtMs = parseExecutorRunTimestamp(strEndedAt);
  if (intEndedAtMs < intStartedAtMs) {
    throw new Error("Executor run state.endedAt cannot be earlier than startedAt.");
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
  expectedStartedAt,
  expectedLogRootPath,
}: {
  filePath: string;
  processPy: ChildProcessWithoutNullStreams;
  getProcessError: () => Error | undefined;
  expectedRunId: string;
  expectedPackageName: string;
  expectedPackageVersion: string;
  expectedStartedAt: string;
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
        expectedStartedAt,
        expectedLogRootPath,
      });
    }

    if (!isProcessRunning(processPy)) {
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
