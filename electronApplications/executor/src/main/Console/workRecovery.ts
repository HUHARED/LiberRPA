// FileName: workRecovery.ts

import fs from "fs";

import { RunStatus, RunOutputsStatus, type RunTerminalStatus } from "../../shared/run";
import { ensureNonEmptyString } from "../Common/validation";
import { getDatabase } from "../Database/connection";
import { dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { RunTerminationReason } from "../Run/types";
import {
  ExecutorRunStateStatus,
  type ExecutorRunState,
  createExecutorRunStatePath,
  readExecutorRunState,
  removeExecutorRunArgumentsFile,
  removeExecutorRunStateFile,
} from "../Run/runState";
import { isRecoveredProcessPresent, watchRecoveredRun } from "../Run/recoveredRuns";
import { ConsoleEventKind, saveConsoleEvent } from "./eventRepository";
import {
  ConsoleWorkState,
  type ConsoleWorkRecord,
  getConsoleWork,
  saveConsoleWork,
  getUnfinishedConsoleWork,
} from "./workRepository";

function recoverFinishedConsoleRun(record: ConsoleWorkRecord): boolean {
  const started = record.started;
  if (!started) return false;
  const strStatePath = createExecutorRunStatePath(record.assignment.run_id);
  if (!fs.existsSync(strStatePath)) return false;
  let state: ExecutorRunState;
  try {
    state = readExecutorRunState({
      filePath: strStatePath,
      expectedRunId: record.assignment.run_id,
      expectedPackageName: ensureNonEmptyString(
        record.assignment.snapshot.project_name,
        "Package name",
      ),
      expectedPackageVersion: ensureNonEmptyString(
        record.assignment.snapshot.project_version,
        "Package version",
      ),
      expectedStartedAt: started.startedAt,
      expectedLogRootPath: started.logPath,
      expectedLogPath: started.logPath,
    });
  } catch {
    return false;
  }
  if (state.status === ExecutorRunStateStatus.Running || !state.endedAt) return false;
  const strEndedAt = state.endedAt;
  const status: RunTerminalStatus =
    state.status === ExecutorRunStateStatus.Terminated
      ? record.stopReason === RunTerminationReason.Timeout
        ? RunStatus.TimedOut
        : RunStatus.Canceled
      : state.status === ExecutorRunStateStatus.Completed
        ? RunStatus.Completed
        : RunStatus.Error;
  const outputs = state.outputs ?? {
    status: RunOutputsStatus.Unavailable,
    values: null,
    unavailableKeys: [],
    reason: "Python did not publish output values.",
  };
  record.ended = {
    ...started,
    endedAt: strEndedAt,
    status,
    retryEligible: status === RunStatus.Error,
    outputs,
    errorSummary: state.errorSummary ?? null,
  };
  record.state = ConsoleWorkState.Finished;
  getDatabase().transaction(() => {
    saveConsoleWork(record);
    saveConsoleEvent(record, {
      kind: ConsoleEventKind.Ended,
      occurred_at: strEndedAt,
      started_at: started.startedAt,
      result: status,
      outputs,
      error_summary: state.errorSummary ?? null,
    });
    dbUpdateRunHistory({
      id: started.historyId,
      run_ended_at_ms: Date.parse(strEndedAt),
      status,
      outputs,
      error_summary: state.errorSummary ?? null,
    });
  })();
  removeExecutorRunStateFile(strStatePath);
  return true;
}

function recoverConsoleRunResult(assignmentId: string): void {
  const record = getConsoleWork(assignmentId);
  if (!record) return;
  // The observer has confirmed process exit, even if its final result is unavailable.
  removeExecutorRunArgumentsFile(record.assignment.run_id);
  recoverFinishedConsoleRun(record);
}

export function recoverConsoleWorkAfterRestart(): void {
  for (const record of getUnfinishedConsoleWork()) {
    if ([ConsoleWorkState.Preparing, ConsoleWorkState.Permitted].includes(record.state)) {
      getDatabase().transaction(() => {
        saveConsoleEvent(record, {
          kind: ConsoleEventKind.NotStarted,
          reason: "Executor restarted before creating the Python process.",
        });
        record.state = ConsoleWorkState.Finished;
        saveConsoleWork(record);
      })();
      continue;
    }
    const started = record.started;
    const boolProcessPresent =
      started?.processId !== undefined && isRecoveredProcessPresent(started.processId);
    if (started?.processId !== undefined && !boolProcessPresent) {
      removeExecutorRunArgumentsFile(record.assignment.run_id);
    }
    if (!boolProcessPresent && recoverFinishedConsoleRun(record)) continue;
    if (record.state !== ConsoleWorkState.Unknown) {
      getDatabase().transaction(() => {
        saveConsoleEvent(record, {
          kind: ConsoleEventKind.Unknown,
          reason: "Executor restarted; the original process result cannot be confirmed.",
        });
        record.state = ConsoleWorkState.Unknown;
        saveConsoleWork(record);
      })();
    }
    if (boolProcessPresent && started?.processId !== undefined) {
      watchRecoveredRun({
        runId: record.assignment.run_id,
        historyId: started.historyId,
        processId: started.processId,
        sessionKey: record.sessionKey,
        onProcessExited: () => recoverConsoleRunResult(record.assignment.id),
      });
    }
  }
}
