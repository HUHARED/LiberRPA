// FileName: eventRepository.ts

import { randomUUID } from "crypto";

import type { RunOutputs, RunEndedStatus, RunRecordingInfo } from "../../shared/run";
import { getDatabase } from "../Database/connection";
import type { RunEndedFact } from "../Run/types";
import { isRecoveredProcessPresent } from "../Run/recoveredRuns";
import type { ConsoleWorkRecord } from "./workRepository";

export enum ConsoleEventKind {
  Started = "started",
  Ended = "ended",
  PreparationFailed = "preparation_failed",
  NotStarted = "not_started",
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
      status: RunEndedStatus;
      outputs: RunOutputs;
      email_output_context: RunEndedFact["emailOutputContext"];
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
      recording: RunRecordingInfo;
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
  work_finished: number | null;
  started_type: string | null;
  ended_type: string | null;
  process_id: number | null;
  logs_finished: number | null;
  record_video: number | null;
  recording_finished: number | null;
  has_pending_work: number;
  has_pending_events: number;
}

const INT_REJECTED_EVENT_RETENTION_MS = 30 * 24 * 60 * 60 * 1000;
const STR_REJECTED_EVENT_RETENTION_SELECT = `
    SELECT
        event.id,
        event.session_key,
        JSON_EXTRACT(event.payload, '$.assignment_id') AS assignment_id,
        event.retention_checked_at_ms,
        event.retention_started_at_ms,
        work.state = 'finished' AS work_finished,
        JSON_TYPE(work.content, '$.started') AS started_type,
        JSON_TYPE(work.content, '$.ended') AS ended_type,
        JSON_EXTRACT(work.content, '$.started.processId') AS process_id,
        JSON_EXTRACT(work.content, '$.logsFinished') AS logs_finished,
        JSON_EXTRACT(
            work.content,
            '$.assignment.snapshot.builtin_record_video'
        ) AS record_video,
        JSON_EXTRACT(work.content, '$.recording.status') IN ('ready', 'unavailable')
            AS recording_finished,
        EXISTS (
            SELECT
                1
            FROM
                console_work AS related_work
            WHERE
                related_work.session_key = event.session_key
                AND JSON_EXTRACT(related_work.content, '$.assignment.job_id')
                    = JSON_EXTRACT(work.content, '$.assignment.job_id')
                AND related_work.state <> 'finished'
        ) AS has_pending_work,
        EXISTS (
            SELECT
                1
            FROM
                console_event AS pending
                JOIN console_work AS pending_work
                    ON pending_work.id = JSON_EXTRACT(pending.payload, '$.assignment_id')
                    AND pending_work.session_key = pending.session_key
            WHERE
                pending.session_key = event.session_key
                AND pending.rejected = 0
                AND JSON_EXTRACT(pending_work.content, '$.assignment.job_id')
                    = JSON_EXTRACT(work.content, '$.assignment.job_id')
        ) AS has_pending_events
    FROM
        console_event AS event
        LEFT JOIN console_work AS work
            ON work.id = JSON_EXTRACT(event.payload, '$.assignment_id')
            AND work.session_key = event.session_key
`;

const INT_MAX_EVENT_REQUEST_BYTES = 1024 * 1024;
const setEventSavedListener = new Set<() => void>();

export function resetConsoleEventRetention(record: ConsoleWorkRecord): void {
  // New work or events reset the retention timer because this Job may still need its diagnostics.
  getDatabase()
    .prepare(
      `
      UPDATE console_event
      SET
          retention_started_at_ms = NULL,
          retention_checked_at_ms = NULL
      WHERE
          rejected = 1
          AND session_key = ?
          AND (
              retention_started_at_ms IS NOT NULL
              OR retention_checked_at_ms IS NOT NULL
          )
          AND JSON_EXTRACT(payload, '$.assignment_id') IN (
              SELECT
                  id
              FROM
                  console_work
              WHERE
                  session_key = ?
                  AND JSON_EXTRACT(content, '$.assignment.job_id') = ?
          );
      `,
    )
    .run(record.sessionKey, record.sessionKey, record.assignment.job_id);
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
  // The response handler has already matched every receipt ID to the submitted batch.
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

function hasRejectedEventWorkFinished(row: RejectedEventRetentionRow): boolean {
  if (
    row.assignment_id === null ||
    row.work_finished !== 1 ||
    row.has_pending_work ||
    row.has_pending_events
  )
    return false;
  if (row.started_type === null) return row.ended_type === null;
  return (
    row.started_type === "object" &&
    row.ended_type === "object" &&
    row.logs_finished === 1 &&
    (row.record_video === 0 || row.recording_finished === 1) &&
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
        WHERE
            event.session_key = ?
            AND event.rejected = 1
            AND event.retention_started_at_ms IS NULL
        ORDER BY
            event.retention_checked_at_ms,
            event.id
        LIMIT
            50;
        `,
      )
      .all(sessionKey) as RejectedEventRetentionRow[];
    const checkEvent = getDatabase().prepare(
      `
      UPDATE console_event
      SET
          retention_checked_at_ms = ?
      WHERE
          id = ?
          AND session_key = ?
          AND rejected = 1
          AND retention_started_at_ms IS NULL;
      `,
    );
    const intCheckedAtMs = Date.now();
    const arrCandidate: ConsoleEventRetentionCandidate[] = [];
    for (const row of arrRow) {
      // Record failed checks too, so the next batch can check later rows instead of repeating the same ones.
      checkEvent.run(intCheckedAtMs, row.id, sessionKey);
      if (hasRejectedEventWorkFinished(row) && row.assignment_id !== null) {
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
        WHERE
            event.session_key = ?
            AND event.rejected = 1
            AND event.retention_started_at_ms IS NULL
            AND event.id IN (${candidates.map(() => "?").join(", ")});
        `,
      )
      .all(sessionKey, ...mapCandidate.keys()) as RejectedEventRetentionRow[];
    const startRetentionPeriod = getDatabase().prepare(
      `
      UPDATE console_event
      SET
          retention_started_at_ms = ?,
          retention_checked_at_ms = ?
      WHERE
          id = ?
          AND session_key = ?
          AND rejected = 1
          AND retention_started_at_ms IS NULL
          AND retention_checked_at_ms = ?;
      `,
    );
    const intRetentionStartedAtMs = Date.now();
    for (const row of arrRow) {
      const candidate = mapCandidate.get(row.id);
      if (
        candidate === undefined ||
        row.assignment_id !== candidate.assignmentId ||
        row.retention_checked_at_ms !== candidate.checkedAtMs ||
        mapResolution.get(candidate.assignmentId) !== (row.started_type === "object") ||
        !hasRejectedEventWorkFinished(row)
      )
        continue;
      // Start the retention period when both sides confirm the work has finished, not when the event was rejected.
      startRetentionPeriod.run(
        intRetentionStartedAtMs,
        intRetentionStartedAtMs,
        row.id,
        sessionKey,
        candidate.checkedAtMs,
      );
    }
  })();
}

export function deleteExpiredConsoleEventDiagnostics(): number {
  return getDatabase().transaction(() => {
    const arrRow = getDatabase()
      .prepare(
        `${STR_REJECTED_EVENT_RETENTION_SELECT}
        WHERE
            event.rejected = 1
            AND event.retention_started_at_ms IS NOT NULL
            AND event.retention_started_at_ms <= ?
        ORDER BY
            event.retention_started_at_ms,
            event.id
        LIMIT
            100;
        `,
      )
      .all(Date.now() - INT_REJECTED_EVENT_RETENTION_MS) as RejectedEventRetentionRow[];
    const deleteEvent = getDatabase().prepare(
      `
      DELETE FROM
          console_event
      WHERE
          id = ?
          AND session_key = ?
          AND rejected = 1
          AND retention_started_at_ms = ?;
      `,
    );
    const resetEvent = getDatabase().prepare(
      `
      UPDATE console_event
      SET
          retention_started_at_ms = NULL,
          retention_checked_at_ms = NULL
      WHERE
          id = ?
          AND session_key = ?
          AND rejected = 1;
      `,
    );
    let intDeleted = 0;
    for (const row of arrRow) {
      if (hasRejectedEventWorkFinished(row)) {
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
