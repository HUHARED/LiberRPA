// FileName: workRecovery.ts

import fs from "fs";

import { RunStatus, RunOutputsStatus, type RunEndedStatus } from "../../shared/run";
import { ensureNonEmptyString } from "../Common/validation";
import { getDatabase } from "../Database/connection";
import { dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { RunTerminationReason } from "../Run/types";
import { notifyRunHistoryChanged } from "../Run/lifecycle";
import {
  ExecutorRunStateStatus,
  type ExecutorRunState,
  createExecutorRunStatePath,
  removeExecutorRunArgumentsFile,
  removeExecutorRunStateFile,
  readExecutorRunState,
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
      expectedProjectName: ensureNonEmptyString(
        record.assignment.snapshot.project_name,
        "Project name",
      ),
      expectedProjectVersion: ensureNonEmptyString(
        record.assignment.snapshot.project_version,
        "Project version",
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
  const status: RunEndedStatus =
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
    retryEligible:
      (record.stopReason === undefined ||
        record.stopReason === RunTerminationReason.Timeout) &&
      (status === RunStatus.Error || status === RunStatus.TimedOut),
    outputs,
    emailOutputContext: state.emailOutputContext ?? null,
    errorSummary: state.errorSummary ?? null,
  };
  record.state = ConsoleWorkState.Finished;
  getDatabase().transaction(() => {
    saveConsoleWork(record);
    saveConsoleEvent(record, {
      kind: ConsoleEventKind.Ended,
      occurred_at: strEndedAt,
      started_at: started.startedAt,
      status,
      outputs,
      email_output_context: state.emailOutputContext ?? null,
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
  notifyRunHistoryChanged(started.historyId);
  removeExecutorRunStateFile(strStatePath);
  return true;
}

function recoverInterruptedConsoleRun(record: ConsoleWorkRecord): void {
  const started = record.started;
  if (!started || record.interruptedAt !== undefined) return;
  const strReason =
    "The original Python process no longer exists; its final result and end time are unavailable.";
  const strInterruptedAt = new Date().toISOString();
  record.interruptedAt = strInterruptedAt;
  record.state = ConsoleWorkState.Unknown;
  getDatabase().transaction(() => {
    saveConsoleWork(record);
    saveConsoleEvent(record, {
      kind: ConsoleEventKind.Unknown,
      occurred_at: strInterruptedAt,
      interrupted_started_at: started.startedAt,
      reason: strReason,
    });
    dbUpdateRunHistory({
      id: started.historyId,
      run_ended_at_ms: null,
      status: RunStatus.Interrupted,
      outputs: {
        status: RunOutputsStatus.Unavailable,
        values: null,
        unavailableKeys: [],
        reason: strReason,
      },
      error_summary: null,
    });
  })();
  notifyRunHistoryChanged(started.historyId);
}

function recoverConsoleRunResult(assignmentId: string): void {
  const record = getConsoleWork(assignmentId);
  if (!record) return;
  // The observer has confirmed process exit, even if its final result is unavailable.
  removeExecutorRunArgumentsFile(record.assignment.run_id);
  if (!recoverFinishedConsoleRun(record)) recoverInterruptedConsoleRun(record);
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
      record.interruptedAt === undefined &&
      started?.processId !== undefined &&
      isRecoveredProcessPresent(started.processId);
    if (started?.processId !== undefined && !boolProcessPresent) {
      removeExecutorRunArgumentsFile(record.assignment.run_id);
    }
    if (!boolProcessPresent && recoverFinishedConsoleRun(record)) continue;
    if (started?.processId !== undefined && !boolProcessPresent) {
      recoverInterruptedConsoleRun(record);
      continue;
    }
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
