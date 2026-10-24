// FileName: eventRepository.ts

import { randomUUID } from "crypto";

import type { RunOutputs, RunEndedStatus, RunRecordingInfo } from "../../shared/run";
import { getDatabase } from "../Database/connection";
import type { RunEndedFact } from "../Run/types";
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

const INT_REJECTED_EVENT_RETENTION_MS = 30 * 24 * 60 * 60 * 1000;
const INT_MAX_EVENT_REQUEST_BYTES = 1024 * 1024;
const setEventSavedListener = new Set<() => void>();

export function onConsoleEventSaved(listener: () => void): () => void {
  setEventSavedListener.add(listener);
  return () => setEventSavedListener.delete(listener);
}

export function saveConsoleEvent(record: ConsoleWorkRecord, event: ConsoleEventData): void {
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

export function deleteExpiredConsoleEventDiagnostics(): number {
  return getDatabase()
    .prepare(
      `
      DELETE FROM
          console_event
      WHERE
          id IN (
              SELECT
                  id
              FROM
                  console_event
              WHERE
                  rejected = 1
                  AND rejected_at_ms <= ?
              ORDER BY
                  rejected_at_ms,
                  id
              LIMIT
                  100
          );
      `,
    )
    .run(Date.now() - INT_REJECTED_EVENT_RETENTION_MS).changes;
}
