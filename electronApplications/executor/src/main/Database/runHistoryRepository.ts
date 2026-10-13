// FileName: runHistoryRepository.ts

import type Database from "better-sqlite3";

import { getErrorMessage } from "../../shared/error";
import {
  RunSource,
  RunOutputsStatus,
  type RunOutputs,
  type RunDetails,
  type ProjectRunConfig,
  RunStatus,
  type RunEndedStatus,
  type RunHistoryQueryOptions,
  type RunHistoryPage,
} from "../../shared/run";

import { loggerMain } from "../Logging/logger";
import { ensureExactRecord, ensureNonEmptyString } from "../Common/validation";
import { getDatabase } from "./connection";
import {
  ensureSingleRowAffected,
  type RunLogLocation,
  ensureRunHistoryListRows,
  ensureCountRow,
  ensureRunHistoryLogLocationRow,
} from "./rowValidation";
import { isRecoveredRunHistoryActive } from "../Run/recoveredRuns";

interface RunHistoryInsertData {
  schedule_name: string | null;
  project_id: number | null;
  source: RunSource;
  run_id: string;
  job_id: string;
  attempt_number: number;
  snapshot: ProjectRunConfig;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  status: RunStatus.Running;
  log_path: string;
}

interface RunHistoryUpdateData {
  id: number;
  run_ended_at_ms: number;
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
  const result = getDatabase()
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
              project_id,
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
      detailDict.project_id,
      detailDict.project_name,
      detailDict.project_version,
      detailDict.python_environment_name,
      detailDict.run_started_at_ms,
      detailDict.status,
      detailDict.log_path,
      intNowMs,
      intNowMs,
    );
  ensureSingleRowAffected(result, "Insert Run History");
  return result;
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
      .prepare(
        `
        SELECT
            1
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

export function dbHasRunningRunForProject(projectId: number): boolean {
  loggerMain.debug("--dbHasRunningRunForProject--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          COUNT(*) AS runningCount
      FROM
          run_history
      WHERE
          status = ?
          AND project_id = ?;
      `,
    )
    .get(RunStatus.Running, projectId);
  return (
    ensureCountRow(row, "runningCount", "Running Run count for Project query result") > 0
  );
}

export function dbSelectRunHistoryLogLocation(id: number): RunLogLocation | undefined {
  loggerMain.debug("--dbSelectRunHistoryLogLocation--");
  const row = getDatabase()
    .prepare(
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
  return row === undefined
    ? undefined
    : ensureRunHistoryLogLocationRow(row, "Run History log location query result");
}

export function dbSelectFinishedLocalRunProjectName(
  runHistoryId: number,
): string | undefined {
  const row = getDatabase()
    .prepare(
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
  if (row === undefined) return undefined;
  const strSourceName = "Run History rerun query result";
  return ensureNonEmptyString(
    ensureExactRecord(row, ["project_name"], strSourceName).project_name,
    `${strSourceName}.project_name`,
  );
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
    .prepare(
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
  const arrRow = ensureRunHistoryListRows(rows, "Run History query result");

  const total = getDatabase()
    .prepare(
      `
      SELECT
          COUNT(*) AS total
      FROM
          run_history
      ${strWhereClause};
      `,
    )
    .get(...arrWhereParam);
  const intTotal = ensureCountRow(total, "total", "Run History count query result");

  return { rows: arrRow, total: intTotal };
}

function parseRetentionLogLocations(rows: unknown[], sourceName: string): RunLogLocation[] {
  const arrLogLocation: RunLogLocation[] = [];
  for (const [intIndex, row] of rows.entries()) {
    try {
      const location = ensureRunHistoryLogLocationRow(row, `${sourceName}[${intIndex}]`);
      if (!isRecoveredRunHistoryActive(location.id)) arrLogLocation.push(location);
    } catch (e: unknown) {
      loggerMain.warn(`Skip invalid Retention log location: ${getErrorMessage(e)}`);
    }
  }
  return arrLogLocation;
}

export function dbSelectLogFolderBefore(cutoffMs: number): RunLogLocation[] {
  loggerMain.debug("--dbSelectLogFolderBefore--");
  const rows = getDatabase()
    .prepare(
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

  return parseRetentionLogLocations(rows, "Expired log folder query result");
}

export function dbSelectVideoBefore(cutoffMs: number): RunLogLocation[] {
  loggerMain.debug("--dbSelectVideoBefore--");
  const rows = getDatabase()
    .prepare(
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

  return parseRetentionLogLocations(rows, "Expired video query result");
}

export function dbSelectVideo(): RunLogLocation[] {
  loggerMain.debug("--dbSelectVideo--");
  const rows = getDatabase()
    .prepare(
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

  return parseRetentionLogLocations(rows, "Video query result");
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
    .prepare(
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
    .get(id) as
    | {
        source: RunSource;
        run_id: string;
        job_id: string;
        attempt_number: number;
        snapshot: string;
        outputs: string;
        error_summary: string | null;
      }
    | undefined;
  if (!row) throw new Error("Run History record not found.");
  return {
    ...row,
    snapshot: JSON.parse(row.snapshot) as ProjectRunConfig,
    outputs: JSON.parse(row.outputs) as RunOutputs,
    error_summary:
      row.error_summary === null
        ? null
        : (JSON.parse(row.error_summary) as RunDetails["error_summary"]),
  };
}
