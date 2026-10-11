// FileName: runState.ts

import type { ChildProcessWithoutNullStreams } from "child_process";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { RunOutputsStatus, type RunOutputs } from "../../shared/run";

import { isProcessRunning } from "../Common/process";
import {
  INT_MAX_CUSTOM_ARGUMENT_JSON_BYTES,
  ensureRecord,
  ensureExactRecord,
  ensureString,
  ensureNonEmptyString,
  ensureJsonValue,
} from "../Common/validation";
import { strDocumentsFolderPath } from "../Config/environment";
import { loggerMain } from "../Logging/logger";
import { ensureRunLogFolderPath, ensureExpectedRunLogFolderPath } from "./logPath";

export enum ExecutorRunStateStatus {
  Running = "running",
  Completed = "completed",
  Error = "error",
  Terminated = "terminated",
}

export interface ExecutorRunState {
  schemaVersion: 1;
  runId: string;
  packageName: string;
  packageVersion: string;
  startedAt: string;
  logPath: string;
  status: ExecutorRunStateStatus;
  endedAt?: string;
  outputs?: RunOutputs;
  errorSummary?: { type: string; message: string } | null;
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
const ARR_FINAL_RUN_STATE_KEY = [
  ...ARR_RUNNING_RUN_STATE_KEY,
  "endedAt",
  "outputs",
  "errorSummary",
] as const;

const strExecutorRunStateFolderPath = path.join(
  strDocumentsFolderPath,
  "LiberRPA/ExecutorRunState",
);

export function createExecutorRunStatePath(runId: string): string {
  fs.mkdirSync(strExecutorRunStateFolderPath, { recursive: true });
  return path.join(strExecutorRunStateFolderPath, `${runId}.json`);
}

export function getExecutorRunArgumentsPath(runId: string): string {
  return path.join(strExecutorRunStateFolderPath, `${runId}.args.json`);
}

export function removeExecutorRunArgumentsFile(runId: string): void {
  try {
    fs.rmSync(getExecutorRunArgumentsPath(runId), { force: true });
  } catch (e: unknown) {
    loggerMain.warn(`Failed to remove arguments for Run ${runId}: ${getErrorMessage(e)}`);
  }
}

export async function cleanExecutorRunArguments(
  canRemoveArguments: (runId: string) => boolean,
): Promise<void> {
  // Startup only: a final state file or elapsed time does not prove process exit.
  const regexArgumentsFile =
    /^([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.args\.json$/i;
  try {
    const directoryStat = await fs.promises.lstat(strExecutorRunStateFolderPath);
    if (!directoryStat.isDirectory()) return;
    const directory = await fs.promises.opendir(strExecutorRunStateFolderPath);
    for await (const entry of directory) {
      if (!entry.isFile()) continue;
      const match = regexArgumentsFile.exec(entry.name);
      if (match && canRemoveArguments(match[1])) removeExecutorRunArgumentsFile(match[1]);
    }
  } catch (e: unknown) {
    if (e instanceof Error && "code" in e && e.code === "ENOENT") return;
    loggerMain.warn(`Failed to clean Executor Run arguments: ${getErrorMessage(e)}`);
  }
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

function ensureExecutorRunStateStatus(value: unknown): ExecutorRunStateStatus {
  switch (value) {
    case ExecutorRunStateStatus.Running:
    case ExecutorRunStateStatus.Completed:
    case ExecutorRunStateStatus.Error:
    case ExecutorRunStateStatus.Terminated:
      return value;
    default:
      throw new Error("Executor run state contains an unsupported status.");
  }
}

function parseRunOutputs(value: unknown): RunOutputs {
  try {
    const dictValue = ensureExactRecord(
      value,
      ["status", "values", "unavailableKeys", "reason"],
      "Run outputs",
    );
    const status = dictValue.status;
    if (
      status !== RunOutputsStatus.Complete &&
      status !== RunOutputsStatus.Partial &&
      status !== RunOutputsStatus.Unavailable
    )
      throw new Error("Invalid Run outputs status.");
    const strReason = ensureString(dictValue.reason, "Run outputs reason");
    if ([...strReason].length > 2000)
      throw new Error("Run outputs reason exceeds the length limit.");
    if (!Array.isArray(dictValue.unavailableKeys))
      throw new Error("Run unavailable keys must be an array.");
    const arrUnavailableKey = dictValue.unavailableKeys.map((key: unknown) =>
      ensureString(key, "Run unavailable key"),
    );
    const setKey = new Set(arrUnavailableKey);
    if (setKey.size !== arrUnavailableKey.length)
      throw new Error("Run unavailable keys contain duplicates.");
    if (
      Buffer.byteLength(JSON.stringify(arrUnavailableKey), "utf8") >
      INT_MAX_CUSTOM_ARGUMENT_JSON_BYTES
    )
      throw new Error("Run unavailable keys exceed the 64 KiB JSON limit.");
    if (status === RunOutputsStatus.Unavailable) {
      if (dictValue.values !== null || arrUnavailableKey.length !== 0)
        throw new Error("Unavailable outputs cannot contain values or keys.");
      return { status, values: null, unavailableKeys: [], reason: strReason };
    }
    if (
      !Array.isArray(dictValue.values) ||
      (status === RunOutputsStatus.Partial) !== arrUnavailableKey.length > 0
    )
      throw new Error("Run outputs do not match their status.");
    // The values budget and depth match the ordered CustomArgs input representation.
    ensureJsonValue(dictValue.values, "Run output values");
    const arrValue: [string, unknown][] = dictValue.values.map((entry: unknown) => {
      if (!Array.isArray(entry) || entry.length !== 2 || typeof entry[0] !== "string")
        throw new Error("A Run output must be a [string, value] pair.");
      if (setKey.has(entry[0])) throw new Error("Run output keys must be unique.");
      setKey.add(entry[0]);
      return [entry[0], entry[1]];
    });
    if (
      Buffer.byteLength(JSON.stringify(arrValue), "utf8") >
      INT_MAX_CUSTOM_ARGUMENT_JSON_BYTES
    )
      throw new Error("Run output values exceed the 64 KiB JSON limit.");
    return {
      status,
      values: arrValue,
      unavailableKeys: arrUnavailableKey,
      reason: strReason,
    };
  } catch {
    return {
      status: RunOutputsStatus.Unavailable,
      values: null,
      unavailableKeys: [],
      reason: "Python returned an invalid or oversized output snapshot.",
    };
  }
}

function parseErrorSummary(value: unknown): { type: string; message: string } | null {
  if (value === null) return null;
  try {
    const dictValue = ensureRecord(value, "Run error summary");
    return {
      type: ensureString(dictValue.type, "Run error type"),
      message: ensureString(dictValue.message, "Run error message"),
    };
  } catch {
    return null;
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
    status === ExecutorRunStateStatus.Running
      ? ARR_RUNNING_RUN_STATE_KEY
      : ARR_FINAL_RUN_STATE_KEY,
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

  if (status === ExecutorRunStateStatus.Running) {
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
    outputs: parseRunOutputs(dictState.outputs),
    errorSummary: parseErrorSummary(dictState.errorSummary),
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
