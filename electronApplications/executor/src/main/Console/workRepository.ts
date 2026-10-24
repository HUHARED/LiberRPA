// FileName: workRepository.ts

import { createHash } from "crypto";

import type { RunRecordingInfo, RunEmailOutputKeys } from "../../shared/run";
import type {
  RunSettings,
  PythonEnvironmentSelection,
  RunConflictPolicy,
} from "../../shared/runSettings";
import { getDatabase } from "../Database/connection";
import type { RunStartedFact, RunEndedFact, RunTerminationReason } from "../Run/types";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import { ConsoleEventKind, saveConsoleEvent } from "./eventRepository";

export enum ConsoleWorkState {
  Preparing = "preparing",
  Permitted = "permitted",
  Launching = "launching",
  Running = "running",
  Finished = "finished",
  Unknown = "unknown",
}

// Only fields used by Executor are typed here; the saved object also keeps fields used only by Console.
export interface ConsoleRunSnapshot extends RunSettings, PythonEnvironmentSelection {
  project_name: string;
  project_version: string;
  sha256: string;
  schedule_name: string | null;
  run_conflict_policy: RunConflictPolicy;
  email_output_keys: RunEmailOutputKeys;
}

export interface ConsoleAssignment {
  id: string;
  job_id: string;
  run_id: string;
  attempt_number: number;
  package_id: string;
  snapshot: ConsoleRunSnapshot;
}

// Keep the raw snapshot so package preparation can report validation failures.
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
  logsFinished: boolean;
  logsUnavailableReason?: string;
  // Saved locally with the pending event; Console may not have received it yet.
  recording?: RunRecordingInfo;
  stopReason?: RunTerminationReason;
}

interface ConsoleWorkRow {
  state: ConsoleWorkState;
  content: string;
}

function parseConsoleWorkRow(row: ConsoleWorkRow): ConsoleWorkRecord {
  return {
    ...(JSON.parse(row.content) as Omit<ConsoleWorkRecord, "state">),
    state: row.state,
  };
}

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
          state,
          content
      FROM
          console_work
      WHERE
          id = ?;
      `,
    )
    .get(id) as ConsoleWorkRow | undefined;
  return row ? parseConsoleWorkRow(row) : undefined;
}

export function saveConsoleWork(record: ConsoleWorkRecord): void {
  const existing = getConsoleWork(record.assignment.id);
  if (existing) {
    record.logOffsets = { ...record.logOffsets, ...existing.logOffsets };
    record.logsFinished ||= existing.logsFinished;
    record.logsUnavailableReason ??= existing.logsUnavailableReason;
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
      JSON.stringify({ ...record, state: undefined }),
      Date.now(),
    );
}

export function getConsoleWorkForRun(
  sessionKey: string,
  runId: string,
): ConsoleWorkRecord | undefined {
  const row = getDatabase()
    .prepare(
      `
      SELECT
          state,
          content
      FROM
          console_work
      WHERE
          session_key = ?
          AND JSON_EXTRACT(content, '$.assignment.run_id') = ?;
      `,
    )
    .get(sessionKey, runId) as ConsoleWorkRow | undefined;
  return row ? parseConsoleWorkRow(row) : undefined;
}

export function getPendingConsoleLogWork(sessionKey: string): ConsoleWorkRecord[] {
  // NOTE: Keep these WHERE conditions aligned with idx_console_work_pending_logs.
  const arrRow = getDatabase()
    .prepare(
      `
      SELECT
          state,
          content
      FROM
          console_work
      WHERE
          session_key = ?
          AND (
              (
                  JSON_TYPE(content, '$.started') = 'object'
                  AND JSON_EXTRACT(content, '$.logsFinished') = 0
              )
              OR (
                  JSON_TYPE(content, '$.ended') = 'object'
                  AND JSON_EXTRACT(
                      content,
                      '$.assignment.snapshot.builtin_record_video'
                  ) = 1
                  AND COALESCE(
                      JSON_EXTRACT(content, '$.recording.status'),
                      ''
                  ) NOT IN ('ready', 'unavailable')
              )
          );
      `,
    )
    .all(sessionKey) as ConsoleWorkRow[];
  return arrRow.map(parseConsoleWorkRow);
}

export function saveConsoleLogProgress(
  id: string,
  offsets: Record<string, number>,
  finished: boolean,
  acknowledgedUnavailableReason?: string,
): void {
  const record = getConsoleWork(id);
  if (!record) return;
  record.logOffsets = offsets;
  // Cleanup may remove the logs while an upload is waiting for a response; keep the reason that still needs to be reported.
  record.logsFinished ||=
    finished &&
    (record.logsUnavailableReason === undefined ||
      record.logsUnavailableReason === acknowledgedUnavailableReason);
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
    .run(JSON.stringify({ ...record, state: undefined }), Date.now(), id);
}

export function markConsoleLogsUnavailable(runId: string, reason: string): void {
  const row = getDatabase()
    .prepare(
      `
      SELECT
          state,
          content
      FROM
          console_work
      WHERE
          JSON_EXTRACT(content, '$.assignment.run_id') = ?;
      `,
    )
    .get(runId) as ConsoleWorkRow | undefined;
  if (!row) return;
  const record = parseConsoleWorkRow(row);
  if (record.logsFinished || record.logsUnavailableReason !== undefined) return;
  record.logsUnavailableReason = reason;
  saveConsoleWork(record);
}

export function reportConsoleRecording(id: string, recording: RunRecordingInfo): void {
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
          JSON_EXTRACT(content, '$.started.processId') AS process_id
      FROM
          console_work
      WHERE
          JSON_EXTRACT(content, '$.assignment.run_id') = ?;
      `,
    )
    .get(runId) as { process_id: unknown } | undefined;
  return typeof row?.process_id === "number" &&
    Number.isSafeInteger(row.process_id) &&
    row.process_id > 0
    ? row.process_id
    : undefined;
}

export function getUnfinishedConsoleWork(): ConsoleWorkRecord[] {
  const arrRow = getDatabase()
    .prepare(
      `
      SELECT
          state,
          content
      FROM
          console_work
      WHERE
          state <> 'finished';
      `,
    )
    .all() as ConsoleWorkRow[];
  return arrRow.map(parseConsoleWorkRow);
}
