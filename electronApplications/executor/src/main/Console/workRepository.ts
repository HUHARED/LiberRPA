// FileName: workRepository.ts

import { createHash, randomUUID } from "crypto";
import fs from "fs";

import {
  type ExecutorRunState,
  createExecutorRunStatePath,
  readExecutorRunState,
  removeExecutorRunStateFile,
} from "../Run/runState";
import { dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { getDatabase } from "../Database/connection";
import type { RunEndedFact, RunStartedFact } from "../Run/types";
import { isRecoveredProcessPresent, watchRecoveredRun } from "../Run/recoveredRuns";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";

export enum ConsoleWorkState {
  Preparing = "preparing",
  Permitted = "permitted",
  Launching = "launching",
  Running = "running",
  Finished = "finished",
  Unknown = "unknown",
}

export enum ConsoleRecordingStatus {
  Recording = "recording",
  Processing = "processing",
  Ready = "ready",
  Unavailable = "unavailable",
}

export interface ConsoleRecordingInfo {
  status: ConsoleRecordingStatus;
  videoSizeBytes?: number | null;
  subtitleSizeBytes?: number | null;
  reason?: string;
}

export interface ConsoleAssignment {
  id: string;
  job_id: string;
  run_id: string;
  attempt: number;
  package_id: string;
  snapshot: Record<string, unknown>;
}

export interface ConsoleWorkRecord {
  assignment: ConsoleAssignment;
  sessionKey: string;
  state: ConsoleWorkState;
  started?: RunStartedFact;
  ended?: RunEndedFact;
  logOffsets: Record<string, number>;
  logsComplete: boolean;
  permitExpiresAt?: string;
  // Persisted with its reliable event; this is not a server acknowledgement.
  recording?: ConsoleRecordingInfo;
  stopReason?: "cancel" | "shutdown" | "timeout";
}

export function getConsoleWorkSessionKey(credential: ConsoleCredentialSnapshot): string {
  return createHash("sha256")
    .update(`${credential.consoleUrl}\n${credential.token}`)
    .digest("hex");
}

export function saveConsoleWork(record: ConsoleWorkRecord): void {
  const existing = getConsoleWork(record.assignment.id);
  if (existing) {
    record.logOffsets = { ...record.logOffsets, ...existing.logOffsets };
    record.logsComplete ||= existing.logsComplete;
    record.recording ??= existing.recording;
  }
  getDatabase()
    .prepare(
      `
      INSERT INTO
          console_work (
              id,
              session_key,
              state,
              content,
              updated_at_ms
          )
      VALUES
          (?, ?, ?, ?, ?)
      ON CONFLICT (id) DO UPDATE
      SET
          state = excluded.state,
          content = excluded.content,
          updated_at_ms = excluded.updated_at_ms;
      `,
    )
    .run(
      record.assignment.id,
      record.sessionKey,
      record.state,
      JSON.stringify(record),
      Date.now(),
    );
}

export function getConsoleWork(id: string): ConsoleWorkRecord | undefined {
  const row = getDatabase()
    .prepare(
      `
      SELECT
          content
      FROM
          console_work
      WHERE
          id = ?;
      `,
    )
    .get(id) as { content: string } | undefined;
  return row ? (JSON.parse(row.content) as ConsoleWorkRecord) : undefined;
}

export function getConsoleWorkForRun(
  sessionKey: string,
  runId: string,
): ConsoleWorkRecord | undefined {
  const row = getDatabase()
    .prepare(
      `
      SELECT
          content
      FROM
          console_work
      WHERE
          session_key = ?
          AND json_extract(content, '$.assignment.run_id') = ?;
      `,
    )
    .get(sessionKey, runId) as { content: string } | undefined;
  return row ? (JSON.parse(row.content) as ConsoleWorkRecord) : undefined;
}

export function getPendingConsoleLogWork(sessionKey: string): ConsoleWorkRecord[] {
  // NOTE: Keep the pending predicate aligned with idx_console_work_pending_logs.
  const arrRow = getDatabase()
    .prepare(
      `
      SELECT
          content
      FROM
          console_work
      WHERE
          session_key = ?
          AND (
              (
                  json_type(content, '$.started') = 'object'
                  AND json_extract(content, '$.logsComplete') = 0
              )
              OR (
                  json_type(content, '$.ended') = 'object'
                  AND json_extract(
                      content,
                      '$.assignment.snapshot.builtin_record_video'
                  ) = 1
                  AND COALESCE(
                      json_extract(content, '$.recording.status'),
                      ''
                  ) NOT IN ('ready', 'unavailable')
              )
          );
      `,
    )
    .all(sessionKey) as { content: string }[];
  return arrRow.map((row) => JSON.parse(row.content) as ConsoleWorkRecord);
}

const INT_MAX_EVENT_REQUEST_BYTES = 1024 * 1024;
const setEventSavedListener = new Set<() => void>();

export function onConsoleEventSaved(listener: () => void): () => void {
  setEventSavedListener.add(listener);
  return () => setEventSavedListener.delete(listener);
}

export function saveConsoleEvent(
  record: ConsoleWorkRecord,
  event: Record<string, unknown>,
): void {
  const strEventId = randomUUID();
  if (typeof event.reason === "string") event.reason = event.reason.slice(0, 2000);
  getDatabase()
    .prepare(
      `
      INSERT INTO
          console_event (
              id,
              session_key,
              payload
          )
      VALUES
          (?, ?, ?);
      `,
    )
    .run(
      strEventId,
      record.sessionKey,
      JSON.stringify({
        event_id: strEventId,
        assignment_id: record.assignment.id,
        occurred_at: new Date().toISOString(),
        ...event,
      }),
    );
  // Notify after the caller's synchronous SQLite transaction has committed.
  queueMicrotask(() => {
    for (const listener of setEventSavedListener) listener();
  });
}

export function getPendingConsoleEvents(sessionKey: string): Record<string, unknown>[] {
  const arrRow = getDatabase()
    .prepare(
      `
      SELECT
          payload
      FROM
          console_event
      WHERE
          session_key = ?
          AND rejected = 0
      ORDER BY
          rowid
      LIMIT
          50;
      `,
    )
    .all(sessionKey) as { payload: string }[];
  const arrEvent: Record<string, unknown>[] = [];
  let intBytes = Buffer.byteLength(JSON.stringify({ events: [] }), "utf8");
  for (const row of arrRow) {
    const event = JSON.parse(row.payload) as Record<string, unknown>;
    const intEventBytes =
      Buffer.byteLength(JSON.stringify(event), "utf8") + (arrEvent.length ? 1 : 0);
    if (intBytes + intEventBytes > INT_MAX_EVENT_REQUEST_BYTES) {
      if (!arrEvent.length)
        throw new Error("A pending Run event exceeds the 1 MiB request limit.");
      break;
    }
    intBytes += intEventBytes;
    arrEvent.push(event);
  }
  return arrEvent;
}

export function acknowledgeConsoleEvents(accepted: string[], rejected: string[]): void {
  getDatabase().transaction(() => {
    for (const strId of accepted)
      getDatabase()
        .prepare(
          `
          DELETE FROM
              console_event
          WHERE
              id = ?;
          `,
        )
        .run(strId);
    for (const strId of rejected)
      getDatabase()
        .prepare(
          `
          UPDATE console_event
          SET
              rejected = 1
          WHERE
              id = ?;
          `,
        )
        .run(strId);
  })();
}

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
      expectedPackageName: String(record.assignment.snapshot.project_name),
      expectedPackageVersion: String(record.assignment.snapshot.project_version),
      expectedStartedAt: started.startedAt,
      expectedLogRootPath: started.logPath,
      expectedLogPath: started.logPath,
    });
  } catch {
    return false;
  }
  if (state.status === "running" || !state.endedAt) return false;
  const strEndedAt = state.endedAt;
  const status =
    state.status === "terminated"
      ? record.stopReason === "timeout"
        ? "timeout"
        : "cancel"
      : state.status;
  const outputs = state.outputs ?? {
    status: "unavailable" as const,
    values: null,
    unavailableKeys: [],
    reason: "Python did not publish output values.",
  };
  record.ended = {
    ...started,
    endedAt: strEndedAt,
    status,
    retryEligible: status === "error",
    outputs,
    errorSummary: state.errorSummary ?? null,
  };
  record.state = ConsoleWorkState.Finished;
  getDatabase().transaction(() => {
    saveConsoleWork(record);
    saveConsoleEvent(record, {
      kind: "ended",
      occurred_at: strEndedAt,
      started_at: started.startedAt,
      result:
        status === "cancel" ? "canceled" : status === "timeout" ? "timed_out" : status,
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
  if (record) recoverFinishedConsoleRun(record);
}

export function recoverConsoleWorkAfterRestart(): void {
  const arrRow = getDatabase()
    .prepare(
      `
      SELECT
          content
      FROM
          console_work
      WHERE
          state <> 'finished';
      `,
    )
    .all() as { content: string }[];
  for (const row of arrRow) {
    const record = JSON.parse(row.content) as ConsoleWorkRecord;
    if ([ConsoleWorkState.Preparing, ConsoleWorkState.Permitted].includes(record.state)) {
      getDatabase().transaction(() => {
        saveConsoleEvent(record, {
          kind: "not_started",
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
    if (!boolProcessPresent && recoverFinishedConsoleRun(record)) continue;
    if (record.state !== ConsoleWorkState.Unknown) {
      getDatabase().transaction(() => {
        saveConsoleEvent(record, {
          kind: "unknown",
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

export function saveConsoleLogProgress(
  id: string,
  offsets: Record<string, number>,
  complete: boolean,
): void {
  const record = getConsoleWork(id);
  if (!record) return;
  record.logOffsets = offsets;
  record.logsComplete ||= complete;
  getDatabase()
    .prepare(
      `
      UPDATE console_work
      SET
          content = ?,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(JSON.stringify(record), Date.now(), id);
}

export function reportConsoleRecording(id: string, recording: ConsoleRecordingInfo): void {
  const record = getConsoleWork(id);
  if (!record) return;
  const previousRecording = record.recording;
  if (
    previousRecording?.status === recording.status &&
    (previousRecording.videoSizeBytes ?? null) === (recording.videoSizeBytes ?? null) &&
    (previousRecording.subtitleSizeBytes ?? null) ===
      (recording.subtitleSizeBytes ?? null) &&
    (previousRecording.reason ?? "") === (recording.reason ?? "")
  )
    return;
  record.recording = recording;
  getDatabase().transaction(() => {
    saveConsoleWork(record);
    saveConsoleEvent(record, { kind: "recording", recording });
  })();
}
