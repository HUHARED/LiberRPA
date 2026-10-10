// FileName: workRepository.ts

import { createHash, randomUUID } from "crypto";
import fs from "fs";

import { type RunOutputs, RunStatus, type RunTerminalStatus } from "../../shared/run";
import type {
  RunConflictPolicy,
  RunOptions,
  PythonEnvironmentSelection,
} from "../../shared/runOptions";

import { ensureNonEmptyString } from "../Common/validation";
import {
  type ExecutorRunState,
  createExecutorRunStatePath,
  removeExecutorRunArgumentsFile,
  removeExecutorRunStateFile,
  readExecutorRunState,
} from "../Run/runState";
import { dbUpdateRunHistory } from "../Database/runHistoryRepository";
import { getDatabase } from "../Database/connection";
import { RunTerminationReason, type RunStartedFact, type RunEndedFact } from "../Run/types";
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

// Only the fields consumed by Executor; the stored payload retains server-only fields.
export interface ConsoleRunSnapshot extends RunOptions, PythonEnvironmentSelection {
  project_name: string;
  project_version: string;
  sha256: string;
  schedule_name: string | null;
  run_conflict_policy: RunConflictPolicy;
}

export interface ConsoleAssignment {
  id: string;
  job_id: string;
  run_id: string;
  attempt: number;
  package_id: string;
  snapshot: ConsoleRunSnapshot;
}

// Keep unvalidated inputs until preparation can report a reliable failure.
export type ConsoleAssignmentData = Omit<ConsoleAssignment, "snapshot"> & {
  snapshot: { [Key in keyof ConsoleRunSnapshot]?: unknown };
};

export interface ConsoleWorkRecord {
  assignment: ConsoleAssignmentData;
  sessionKey: string;
  state: ConsoleWorkState;
  started?: RunStartedFact;
  ended?: RunEndedFact;
  logOffsets: Record<string, number>;
  logsComplete: boolean;
  permitExpiresAt?: string;
  // Persisted with its reliable event; this is not a server acknowledgement.
  recording?: ConsoleRecordingInfo;
  stopReason?: RunTerminationReason;
}

export enum ConsoleEventKind {
  PreparationFailed = "preparation_failed",
  Started = "started",
  NotStarted = "not_started",
  Ended = "ended",
  Unknown = "unknown",
  Recording = "recording",
}

export enum ConsoleNotStartedReason {
  LocalConflict = "local_conflict",
}

export type ConsoleEventData =
  | {
      kind: ConsoleEventKind.Started;
      occurred_at: string;
      started_at: string;
    }
  | {
      kind: ConsoleEventKind.Ended;
      occurred_at: string;
      started_at: string;
      result: RunTerminalStatus;
      outputs: RunOutputs;
      error_summary: RunEndedFact["errorSummary"];
    }
  | {
      kind: ConsoleEventKind.NotStarted;
      reason: string;
      not_started_reason?: ConsoleNotStartedReason;
    }
  | {
      kind: ConsoleEventKind.PreparationFailed | ConsoleEventKind.Unknown;
      reason: string;
    }
  | {
      kind: ConsoleEventKind.Recording;
      recording: ConsoleRecordingInfo;
    };

export type ConsoleEvent = ConsoleEventData & {
  event_id: string;
  assignment_id: string;
  occurred_at: string;
};

export interface ConsoleEventRejection {
  eventId: string;
  code: string;
  message: string;
}

export interface ConsoleEventReceipt {
  acceptedEventIds: string[];
  rejectedEvents: ConsoleEventRejection[];
}

export interface ConsoleEventRetentionCandidate {
  eventId: string;
  assignmentId: string;
  checkedAtMs: number;
}

export interface ConsoleEventRetentionResolution {
  assignmentId: string;
  runStarted: boolean;
}

interface RejectedEventRetentionRow {
  id: string;
  session_key: string;
  assignment_id: string | null;
  retention_checked_at_ms: number | null;
  retention_started_at_ms: number | null;
  work_state: ConsoleWorkState | null;
  started_type: string | null;
  ended_type: string | null;
  process_id: number | null;
  logs_complete: number | null;
  record_video: number | null;
  recording_status: ConsoleRecordingStatus | null;
  has_pending_work: number;
  has_pending_events: number;
}

const INT_REJECTED_EVENT_RETENTION_MS = 30 * 24 * 60 * 60 * 1000;
const STR_REJECTED_EVENT_RETENTION_SELECT = `
    SELECT
        event.id,
        event.session_key,
        json_extract(event.payload, '$.assignment_id') AS assignment_id,
        event.retention_checked_at_ms,
        event.retention_started_at_ms,
        work.state AS work_state,
        json_type(work.content, '$.started') AS started_type,
        json_type(work.content, '$.ended') AS ended_type,
        json_extract(work.content, '$.started.processId') AS process_id,
        json_extract(work.content, '$.logsComplete') AS logs_complete,
        json_extract(work.content, '$.assignment.snapshot.builtin_record_video')
            AS record_video,
        json_extract(work.content, '$.recording.status') AS recording_status,
        EXISTS (
            SELECT 1 FROM console_work AS related_work
            WHERE related_work.session_key = event.session_key
                AND json_extract(related_work.content, '$.assignment.job_id')
                    = json_extract(work.content, '$.assignment.job_id')
                AND related_work.state <> 'finished'
        ) AS has_pending_work,
        EXISTS (
            SELECT 1 FROM console_event AS pending
            JOIN console_work AS pending_work
                ON pending_work.id = json_extract(pending.payload, '$.assignment_id')
                AND pending_work.session_key = pending.session_key
            WHERE pending.session_key = event.session_key AND pending.rejected = 0
                AND json_extract(pending_work.content, '$.assignment.job_id')
                    = json_extract(work.content, '$.assignment.job_id')
        ) AS has_pending_events
    FROM console_event AS event
    LEFT JOIN console_work AS work
        ON work.id = json_extract(event.payload, '$.assignment_id')
        AND work.session_key = event.session_key
`;

const INT_MAX_EVENT_REQUEST_BYTES = 1024 * 1024;
const setEventSavedListener = new Set<() => void>();

export function getConsoleWorkSessionKey(credential: ConsoleCredentialSnapshot): string {
  return createHash("sha256")
    .update(`${credential.consoleUrl}\n${credential.token}`)
    .digest("hex");
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

function resetConsoleEventRetention(record: ConsoleWorkRecord): void {
  // New local work or facts invalidate a previously observed quiet period for this Job.
  getDatabase()
    .prepare(
      `
      UPDATE console_event
      SET retention_started_at_ms = NULL, retention_checked_at_ms = NULL
      WHERE rejected = 1 AND session_key = ?
          AND (retention_started_at_ms IS NOT NULL OR retention_checked_at_ms IS NOT NULL)
          AND json_extract(payload, '$.assignment_id') IN (
              SELECT id FROM console_work
              WHERE session_key = ? AND json_extract(content, '$.assignment.job_id') = ?
          );
      `,
    )
    .run(record.sessionKey, record.sessionKey, record.assignment.job_id);
}

export function saveConsoleWork(record: ConsoleWorkRecord): void {
  resetConsoleEventRetention(record);
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

export function onConsoleEventSaved(listener: () => void): () => void {
  setEventSavedListener.add(listener);
  return () => setEventSavedListener.delete(listener);
}

export function saveConsoleEvent(record: ConsoleWorkRecord, event: ConsoleEventData): void {
  resetConsoleEventRetention(record);
  const strEventId = randomUUID();
  const eventPayload: ConsoleEvent = {
    ...event,
    event_id: strEventId,
    assignment_id: record.assignment.id,
    occurred_at: "occurred_at" in event ? event.occurred_at : new Date().toISOString(),
  };
  if ("reason" in eventPayload) eventPayload.reason = eventPayload.reason.slice(0, 2000);
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
    .run(strEventId, record.sessionKey, JSON.stringify(eventPayload));
  // Notify after the caller's synchronous SQLite transaction has committed.
  queueMicrotask(() => {
    for (const listener of setEventSavedListener) listener();
  });
}

export function getPendingConsoleEvents(sessionKey: string): ConsoleEvent[] {
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
  const arrEvent: ConsoleEvent[] = [];
  let intBytes = Buffer.byteLength(JSON.stringify({ events: [] }), "utf8");
  for (const row of arrRow) {
    const event = JSON.parse(row.payload) as ConsoleEvent;
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

export function acknowledgeConsoleEvents(
  sessionKey: string,
  receipt: ConsoleEventReceipt,
): number {
  // The HTTP boundary has matched every receipt ID to the submitted batch.
  return getDatabase().transaction(() => {
    const deleteAccepted = getDatabase().prepare(
      `
      DELETE FROM
          console_event
      WHERE
          id = ?
          AND session_key = ?
          AND rejected = 0;
      `,
    );
    const saveRejection = getDatabase().prepare(
      `
      UPDATE console_event
      SET
          rejected = 1,
          rejection_code = ?,
          rejection_message = ?,
          rejected_at_ms = ?
      WHERE
          id = ?
          AND session_key = ?
          AND rejected = 0;
      `,
    );
    // This is receipt time on Executor, not the original event's occurrence time.
    const intRejectedAtMs = Date.now();
    for (const strId of receipt.acceptedEventIds) deleteAccepted.run(strId, sessionKey);
    let intRejectedCount = 0;
    for (const rejection of receipt.rejectedEvents) {
      intRejectedCount += saveRejection.run(
        rejection.code,
        rejection.message,
        intRejectedAtMs,
        rejection.eventId,
        sessionKey,
      ).changes;
    }
    return intRejectedCount;
  })();
}

function isRejectedEventLocallySettled(row: RejectedEventRetentionRow): boolean {
  if (
    row.assignment_id === null ||
    row.work_state !== ConsoleWorkState.Finished ||
    row.has_pending_work ||
    row.has_pending_events
  )
    return false;
  if (row.started_type === null) return row.ended_type === null;
  return (
    row.started_type === "object" &&
    row.ended_type === "object" &&
    row.logs_complete === 1 &&
    (row.record_video === 0 ||
      row.recording_status === ConsoleRecordingStatus.Ready ||
      row.recording_status === ConsoleRecordingStatus.Unavailable) &&
    row.process_id !== null &&
    Number.isSafeInteger(row.process_id) &&
    row.process_id > 0 &&
    !isRecoveredProcessPresent(row.process_id)
  );
}

export function getConsoleEventRetentionCandidates(
  sessionKey: string,
): ConsoleEventRetentionCandidate[] {
  return getDatabase().transaction(() => {
    const arrRow = getDatabase()
      .prepare(
        `${STR_REJECTED_EVENT_RETENTION_SELECT}
        WHERE event.session_key = ? AND event.rejected = 1
            AND event.retention_started_at_ms IS NULL
        ORDER BY event.retention_checked_at_ms, event.id
        LIMIT 50;
        `,
      )
      .all(sessionKey) as RejectedEventRetentionRow[];
    const checkEvent = getDatabase().prepare(
      `
      UPDATE console_event SET retention_checked_at_ms = ?
      WHERE id = ? AND session_key = ? AND rejected = 1
          AND retention_started_at_ms IS NULL;
      `,
    );
    const intCheckedAtMs = Date.now();
    const arrCandidate: ConsoleEventRetentionCandidate[] = [];
    for (const row of arrRow) {
      // Remember unsuccessful checks too, so unresolved old rows cannot starve later ones.
      checkEvent.run(intCheckedAtMs, row.id, sessionKey);
      if (isRejectedEventLocallySettled(row) && row.assignment_id !== null) {
        arrCandidate.push({
          eventId: row.id,
          assignmentId: row.assignment_id,
          checkedAtMs: intCheckedAtMs,
        });
      }
    }
    return arrCandidate;
  })();
}

export function confirmConsoleEventRetention(
  sessionKey: string,
  candidates: ConsoleEventRetentionCandidate[],
  resolutions: ConsoleEventRetentionResolution[],
): void {
  if (!candidates.length || !resolutions.length) return;
  const mapCandidate = new Map(candidates.map((entry) => [entry.eventId, entry]));
  const mapResolution = new Map(
    resolutions.map((entry) => [entry.assignmentId, entry.runStarted]),
  );
  getDatabase().transaction(() => {
    const arrRow = getDatabase()
      .prepare(
        `${STR_REJECTED_EVENT_RETENTION_SELECT}
        WHERE event.session_key = ? AND event.rejected = 1
            AND event.retention_started_at_ms IS NULL
            AND event.id IN (${candidates.map(() => "?").join(", ")});
        `,
      )
      .all(sessionKey, ...mapCandidate.keys()) as RejectedEventRetentionRow[];
    const markSettled = getDatabase().prepare(
      `
      UPDATE console_event
      SET retention_started_at_ms = ?, retention_checked_at_ms = ?
      WHERE id = ? AND session_key = ? AND rejected = 1
          AND retention_started_at_ms IS NULL AND retention_checked_at_ms = ?;
      `,
    );
    const intSettledAtMs = Date.now();
    for (const row of arrRow) {
      const candidate = mapCandidate.get(row.id);
      if (
        candidate === undefined ||
        row.assignment_id !== candidate.assignmentId ||
        row.retention_checked_at_ms !== candidate.checkedAtMs ||
        mapResolution.get(candidate.assignmentId) !== (row.started_type === "object") ||
        !isRejectedEventLocallySettled(row)
      )
        continue;
      // Start locally observed retention now, not at the earlier rejection or Run end.
      markSettled.run(
        intSettledAtMs,
        intSettledAtMs,
        row.id,
        sessionKey,
        candidate.checkedAtMs,
      );
    }
  })();
}

export function pruneConsoleEventDiagnostics(): number {
  return getDatabase().transaction(() => {
    const arrRow = getDatabase()
      .prepare(
        `${STR_REJECTED_EVENT_RETENTION_SELECT}
        WHERE event.rejected = 1 AND event.retention_started_at_ms IS NOT NULL
            AND event.retention_started_at_ms <= ?
        ORDER BY event.retention_started_at_ms, event.id
        LIMIT 100;
        `,
      )
      .all(Date.now() - INT_REJECTED_EVENT_RETENTION_MS) as RejectedEventRetentionRow[];
    const deleteEvent = getDatabase().prepare(
      `
      DELETE FROM console_event WHERE id = ? AND session_key = ? AND rejected = 1
          AND retention_started_at_ms = ?;
      `,
    );
    const resetEvent = getDatabase().prepare(
      `
      UPDATE console_event
      SET retention_started_at_ms = NULL, retention_checked_at_ms = NULL
      WHERE id = ? AND session_key = ? AND rejected = 1;
      `,
    );
    let intDeleted = 0;
    for (const row of arrRow) {
      if (isRejectedEventLocallySettled(row)) {
        intDeleted += deleteEvent.run(
          row.id,
          row.session_key,
          row.retention_started_at_ms,
        ).changes;
      } else {
        resetEvent.run(row.id, row.session_key);
      }
    }
    return intDeleted;
  })();
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

export function saveConsoleLogProgress(
  id: string,
  offsets: Record<string, number>,
  complete: boolean,
): void {
  const record = getConsoleWork(id);
  if (!record) return;
  resetConsoleEventRetention(record);
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
    saveConsoleEvent(record, { kind: ConsoleEventKind.Recording, recording });
  })();
}

export function getConsoleRunProcessId(runId: string): number | undefined {
  const row = getDatabase()
    .prepare(
      `
      SELECT
          json_extract(content, '$.started.processId') AS process_id
      FROM
          console_work
      WHERE
          json_extract(content, '$.assignment.run_id') = ?;
      `,
    )
    .get(runId) as { process_id: unknown } | undefined;
  return typeof row?.process_id === "number" &&
    Number.isSafeInteger(row.process_id) &&
    row.process_id > 0
    ? row.process_id
    : undefined;
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
  if (state.status === "running" || !state.endedAt) return false;
  const strEndedAt = state.endedAt;
  const status: RunTerminalStatus =
    state.status === "terminated"
      ? record.stopReason === RunTerminationReason.Timeout
        ? RunStatus.TimedOut
        : RunStatus.Canceled
      : state.status === "completed"
        ? RunStatus.Completed
        : RunStatus.Error;
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
