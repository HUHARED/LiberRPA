// FileName: runHistoryRepository.ts

import type Database from "better-sqlite3";

import {
  RunSource,
  RunOutputsStatus,
  type RunOutputs,
  type RunDetails,
  type RunConfig,
  RunStatus,
  type RunEndedStatus,
  type RunHistoryItem,
  type RunHistoryQueryOptions,
  type RunHistoryPage,
} from "../../shared/run";

import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import { ensureSingleRowAffected } from "./rowConversion";
import { isRecoveredRunHistoryActive } from "../Run/recoveredRuns";

export interface RunLogLocation {
  id: number;
  run_id: string;
  log_path: string;
  record_video: boolean;
  finished_at_ms: number;
}

type RunLogLocationRow = Omit<RunLogLocation, "record_video"> & { record_video: 0 | 1 };
type RunDetailsRow = Omit<RunDetails, "snapshot" | "outputs" | "error_summary"> & {
  snapshot: string;
  outputs: string;
  error_summary: string | null;
};

interface RunHistoryInsertData {
  schedule_name: string | null;
  local_package_id: number | null;
  source: RunSource;
  run_id: string;
  job_id: string;
  attempt_number: number;
  snapshot: RunConfig;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  status: RunStatus.Running;
  log_path: string;
}

interface RunHistoryUpdateData {
  id: number;
  run_ended_at_ms: number | null;
  status: RunEndedStatus;
  outputs: RunOutputs;
  error_summary: { type: string; message: string } | null;
}

const MAP_RUN_HISTORY_SORT_COLUMN: Record<
  RunHistoryQueryOptions["sortBy"][number]["key"],
  string
> = {
  schedule_name: "schedule_name",
  project_name: "project_name",
  project_version: "project_version",
  run_started_at_ms: "run_started_at_ms",
  run_ended_at_ms: "run_ended_at_ms",
  status: "status",
};

export function dbInsertRunHistory(detailDict: RunHistoryInsertData): Database.RunResult {
  loggerMain.debug("--dbInsertRunHistory--");
  const intNowMs = Date.now();
  return getDatabase()
    .prepare(
      `
      INSERT INTO
          run_history (
              source,
              run_id,
              job_id,
              attempt_number,
              snapshot,
              outputs,
              schedule_name,
              local_package_id,
              project_name,
              project_version,
              python_environment_name,
              run_started_at_ms,
              status,
              log_path,
              created_at_ms,
              updated_at_ms
          )
      VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
      detailDict.source,
      detailDict.run_id,
      detailDict.job_id,
      detailDict.attempt_number,
      JSON.stringify(detailDict.snapshot),
      JSON.stringify({
        status: RunOutputsStatus.Unavailable,
        values: null,
        unavailableKeys: [],
        reason: "The Run has not produced an output snapshot.",
      }),
      detailDict.schedule_name,
      detailDict.local_package_id,
      detailDict.project_name,
      detailDict.project_version,
      detailDict.python_environment_name,
      detailDict.run_started_at_ms,
      detailDict.status,
      detailDict.log_path,
      intNowMs,
      intNowMs,
    );
}

export function dbUpdateRunHistory(detailDict: RunHistoryUpdateData): void {
  loggerMain.debug("--dbUpdateRunHistory--");
  const result = getDatabase()
    .prepare(
      `
      UPDATE run_history
      SET
          outputs = ?,
          error_summary = ?,
          run_ended_at_ms = ?,
          status = ?,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(
      JSON.stringify(detailDict.outputs),
      JSON.stringify(detailDict.error_summary),
      detailDict.run_ended_at_ms,
      detailDict.status,
      Date.now(),
      detailDict.id,
    );
  ensureSingleRowAffected(result, `Finalize Run History ID ${detailDict.id}`);
}

export function dbMarkUnfinishedRunsAfterRestart(): void {
  loggerMain.debug("--dbMarkUnfinishedRunsAfterRestart--");
  const result = getDatabase()
    .prepare(
      `
      UPDATE run_history
      SET
          run_ended_at_ms = NULL,
          status = CASE source WHEN ? THEN ? ELSE ? END,
          updated_at_ms = ?
      WHERE
          status = ?;
      `,
    )
    .run(
      RunSource.Local,
      RunStatus.Interrupted,
      RunStatus.Unknown,
      Date.now(),
      RunStatus.Running,
    );

  if (result.changes > 0) {
    loggerMain.warn(
      `Updated ${result.changes} unfinished local and Console Run(s) after restart.`,
    );
  }
}

export function dbHasEndedLocalRun(runId: string): boolean {
  // Recovery after restart leaves the end time empty; a finished status alone does not confirm when the process ended.
  return (
    getDatabase()
      .prepare<[string, RunSource], { found: 1 }>(
        `
        SELECT
            1 AS found
        FROM
            run_history
        WHERE
            run_id = ?
            AND source = ?
            AND run_ended_at_ms IS NOT NULL;
        `,
      )
      .get(runId, RunSource.Local) !== undefined
  );
}

export function dbHasRunningRunForPackage(packageId: number): boolean {
  loggerMain.debug("--dbHasRunningRunForPackage--");
  return (
    getDatabase()
      .prepare<[RunStatus, number], { found: 1 }>(
        `
        SELECT
            1 AS found
        FROM
            run_history
        WHERE
            status = ?
            AND local_package_id = ?
        LIMIT
            1;
        `,
      )
      .get(RunStatus.Running, packageId) !== undefined
  );
}

function convertRunLogLocationRow(row: RunLogLocationRow): RunLogLocation {
  return { ...row, record_video: row.record_video === 1 };
}

export function dbSelectRunHistoryLogLocation(id: number): RunLogLocation | undefined {
  loggerMain.debug("--dbSelectRunHistoryLogLocation--");
  const row = getDatabase()
    .prepare<[number], RunLogLocationRow>(
      `
      SELECT
          id,
          run_id,
          log_path,
          JSON_EXTRACT(snapshot, '$.builtin_record_video') AS record_video,
          COALESCE(run_ended_at_ms, updated_at_ms) AS finished_at_ms
      FROM
          run_history
      WHERE
          id = ?;
      `,
    )
    .get(id);
  return row === undefined ? undefined : convertRunLogLocationRow(row);
}

export function dbSelectFinishedLocalRunProjectName(
  runHistoryId: number,
): string | undefined {
  const row = getDatabase()
    .prepare<[number, RunSource, RunStatus, RunStatus], { project_name: string }>(
      `
      SELECT
          project_name
      FROM
          run_history
      WHERE
          id = ?
          AND source = ?
          AND run_ended_at_ms IS NOT NULL
          AND status NOT IN (?, ?);
      `,
    )
    .get(runHistoryId, RunSource.Local, RunStatus.Running, RunStatus.Unknown);
  return row?.project_name;
}

export function dbSelectRunHistoryPage(options: RunHistoryQueryOptions): RunHistoryPage {
  loggerMain.debug("--dbSelectRunHistoryPage--");

  // Request options have already been validated at the IPC boundary.
  const arrWhereClause: string[] = [];
  const arrWhereParam: string[] = [];
  if (options.search.schedule_name.trim() !== "") {
    arrWhereClause.push("schedule_name LIKE ?");
    arrWhereParam.push(`%${options.search.schedule_name.trim()}%`);
  }
  if (options.search.project_name.trim() !== "") {
    arrWhereClause.push("project_name LIKE ?");
    arrWhereParam.push(`%${options.search.project_name.trim()}%`);
  }
  if (options.search.project_version.trim() !== "") {
    arrWhereClause.push("project_version LIKE ?");
    arrWhereParam.push(`%${options.search.project_version.trim()}%`);
  }
  if (options.search.status !== null) {
    arrWhereClause.push("status = ?");
    arrWhereParam.push(options.search.status);
  }

  if (options.search.source !== null) {
    arrWhereClause.push("source = ?");
    arrWhereParam.push(options.search.source);
  }

  const strWhereClause =
    arrWhereClause.length === 0 ? "" : `WHERE ${arrWhereClause.join(" AND ")}`;

  const arrOrderByClause = options.sortBy.map((dictSort) => {
    const strColumn = MAP_RUN_HISTORY_SORT_COLUMN[dictSort.key];
    const strOrder = dictSort.order === "asc" ? "ASC" : "DESC";
    return `${strColumn} ${strOrder}`;
  });
  arrOrderByClause.push("run_started_at_ms DESC", "id DESC");
  const strOrderByClause = arrOrderByClause.join(", ");

  const rows = getDatabase()
    .prepare<(string | number)[], RunHistoryItem>(
      `
      SELECT
          id,
          source,
          attempt_number,
          schedule_name,
          project_name,
          project_version,
          run_started_at_ms,
          run_ended_at_ms,
          status
      FROM
          run_history
      ${strWhereClause}
      ORDER BY
          ${strOrderByClause}
      LIMIT
          ?
      OFFSET
          ?;
      `,
    )
    .all(...arrWhereParam, options.itemsPerPage, (options.page - 1) * options.itemsPerPage);

  // COUNT(*) without GROUP BY always returns one row, even when no Runs match.
  const rowCount = getDatabase()
    .prepare<string[], { total: number }>(
      `
      SELECT
          COUNT(*) AS total
      FROM
          run_history
      ${strWhereClause};
      `,
    )
    .get(...arrWhereParam)!;

  return { rows, total: rowCount.total };
}

function getRetentionLogLocations(rows: RunLogLocationRow[]): RunLogLocation[] {
  return rows
    .filter((row) => !isRecoveredRunHistoryActive(row.id))
    .map(convertRunLogLocationRow);
}

export function dbSelectLogFolderBefore(cutoffMs: number): RunLogLocation[] {
  loggerMain.debug("--dbSelectLogFolderBefore--");
  const rows = getDatabase()
    .prepare<[RunStatus, number], RunLogLocationRow>(
      `
      SELECT
          id,
          run_id,
          log_path,
          JSON_EXTRACT(snapshot, '$.builtin_record_video') AS record_video,
          COALESCE(run_ended_at_ms, updated_at_ms) AS finished_at_ms
      FROM
          run_history
      WHERE
          status <> ?
          AND no_log_folder = 0
          AND COALESCE(run_ended_at_ms, run_started_at_ms) < ?
      ORDER BY
          COALESCE(run_ended_at_ms, run_started_at_ms) DESC;
      `,
    )
    .all(RunStatus.Running, cutoffMs);

  return getRetentionLogLocations(rows);
}

export function dbSelectVideoBefore(cutoffMs: number): RunLogLocation[] {
  loggerMain.debug("--dbSelectVideoBefore--");
  const rows = getDatabase()
    .prepare<[RunStatus, number], RunLogLocationRow>(
      `
      SELECT
          id,
          run_id,
          log_path,
          JSON_EXTRACT(snapshot, '$.builtin_record_video') AS record_video,
          COALESCE(run_ended_at_ms, updated_at_ms) AS finished_at_ms
      FROM
          run_history
      WHERE
          status <> ?
          AND no_log_video = 0
          AND COALESCE(run_ended_at_ms, run_started_at_ms) < ?
      ORDER BY
          COALESCE(run_ended_at_ms, run_started_at_ms) DESC;
      `,
    )
    .all(RunStatus.Running, cutoffMs);

  return getRetentionLogLocations(rows);
}

export function dbSelectVideo(): RunLogLocation[] {
  loggerMain.debug("--dbSelectVideo--");
  const rows = getDatabase()
    .prepare<[RunStatus], RunLogLocationRow>(
      `
      SELECT
          id,
          run_id,
          log_path,
          JSON_EXTRACT(snapshot, '$.builtin_record_video') AS record_video,
          COALESCE(run_ended_at_ms, updated_at_ms) AS finished_at_ms
      FROM
          run_history
      WHERE
          status <> ?
          AND no_log_video = 0
      ORDER BY
          COALESCE(run_ended_at_ms, run_started_at_ms) DESC;
      `,
    )
    .all(RunStatus.Running);

  return getRetentionLogLocations(rows);
}

export function dbUpdateNoLogFolderAndVideo(runHistoryId: number): void {
  loggerMain.debug("--dbUpdateNoLogFolderAndVideo--");
  getDatabase()
    .prepare(
      `
      UPDATE run_history
      SET
          no_log_folder = 1,
          no_log_video = 1,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(Date.now(), runHistoryId);
}

export function dbUpdateNoVideo(runHistoryId: number): void {
  loggerMain.debug("--dbUpdateNoVideo--");
  getDatabase()
    .prepare(
      `
      UPDATE run_history
      SET
          no_log_video = 1,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(Date.now(), runHistoryId);
}

export function dbSelectRunDetails(id: number): RunDetails {
  const row = getDatabase()
    .prepare<[number], RunDetailsRow>(
      `
      SELECT
          source,
          run_id,
          job_id,
          attempt_number,
          snapshot,
          outputs,
          error_summary
      FROM
          run_history
      WHERE
          id = ?;
      `,
    )
    .get(id);
  if (row === undefined) throw new Error("Run History record not found.");
  return {
    ...row,
    snapshot: JSON.parse(row.snapshot) as RunConfig,
    outputs: JSON.parse(row.outputs) as RunOutputs,
    error_summary:
      row.error_summary === null
        ? null
        : (JSON.parse(row.error_summary) as RunDetails["error_summary"]),
  };
}
