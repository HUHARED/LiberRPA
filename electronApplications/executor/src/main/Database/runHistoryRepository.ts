// FileName: runHistoryRepository.ts

import type Database from "better-sqlite3";

import { getErrorMessage } from "../../shared/error";
import type {
  Dict_RunHistory_Options,
  Dict_RunHistory_Page,
  Str_RunHistory_Status,
} from "../../shared/run";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  type Dict_RunHistory_LogLocation,
  ensureCountRow,
  ensureRunHistoryLogLocationRow,
  ensureRunHistoryListRows,
  ensureSingleRowAffected,
} from "./rowValidation";

interface Dict_RunHistory_Insert {
  schedule_name: string | null;
  project_id: number;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  status: "running";
  log_path: string;
}

interface Dict_RunHistory_Update {
  id: number;
  run_ended_at_ms: number;
  status: "completed" | "error" | "cancel" | "timeout";
}

const MAP_RUN_HISTORY_SORT_COLUMN: Record<
  Dict_RunHistory_Options["sortBy"][number]["key"],
  string
> = {
  schedule_name: "schedule_name",
  project_name: "project_name",
  project_version: "project_version",
  python_environment_name: "python_environment_name",
  run_started_at_ms: "run_started_at_ms",
  run_ended_at_ms: "run_ended_at_ms",
  status: "status",
};

export function dbInsertRunHistory(detailDict: Dict_RunHistory_Insert): Database.RunResult {
  loggerMain.debug("--dbInsertRunHistory--");
  const intNowMs = Date.now();
  const result = getDatabase()
    .prepare(
      `
      INSERT INTO
          run_history (
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
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
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

export function dbUpdateRunHistory(detailDict: Dict_RunHistory_Update): void {
  loggerMain.debug("--dbUpdateRunHistory--");
  const result = getDatabase()
    .prepare(
      `
      UPDATE run_history
      SET
          run_ended_at_ms = ?,
          status = ?,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(detailDict.run_ended_at_ms, detailDict.status, Date.now(), detailDict.id);
  ensureSingleRowAffected(result, `Finalize Run History ID ${detailDict.id}`);
}

export function dbMarkRunningRunsInterrupted(): void {
  loggerMain.debug("--dbMarkRunningRunsInterrupted--");
  const result = getDatabase()
    .prepare(
      `
      UPDATE run_history
      SET
          run_ended_at_ms = NULL,
          status = 'interrupted',
          updated_at_ms = ?
      WHERE
          status = 'running';
      `,
    )
    .run(Date.now());

  if (result.changes > 0) {
    loggerMain.warn(`Marked ${result.changes} unfinished Run(s) as interrupted.`);
  }
}

export function dbHasRunningRun(): boolean {
  // loggerMain.debug("--dbHasRunningRun--"); It's too frequent.
  const row = getDatabase()
    .prepare("SELECT COUNT(*) AS runningCount FROM run_history WHERE status = 'running';")
    .get();
  return ensureCountRow(row, "runningCount", "Running Run count query result") > 0;
}

export function dbHasRunningRunForProject(projectId: number): boolean {
  loggerMain.debug("--dbHasRunningRunForProject--");
  const row = getDatabase()
    .prepare(
      "SELECT COUNT(*) AS runningCount FROM run_history WHERE status = 'running' AND project_id = ?;",
    )
    .get(projectId);
  return (
    ensureCountRow(row, "runningCount", "Running Run count for Project query result") > 0
  );
}

export function dbSelectRunHistoryLogLocation(
  id: number,
): Dict_RunHistory_LogLocation | undefined {
  loggerMain.debug("--dbSelectRunHistoryLogLocation--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          log_path
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

export function dbSelectRunHistoryPage(
  options: Dict_RunHistory_Options,
): Dict_RunHistory_Page {
  loggerMain.debug("--dbSelectRunHistoryPage--");

  if (!Number.isSafeInteger(options.page) || options.page < 1) {
    throw new Error(`Invalid Run History page: ${String(options.page)}`);
  }
  if (!Number.isSafeInteger(options.itemsPerPage) || options.itemsPerPage < 1) {
    throw new Error(`Invalid Run History itemsPerPage: ${String(options.itemsPerPage)}`);
  }
  if (!Array.isArray(options.sortBy)) {
    throw new Error("Run History sortBy must be an array.");
  }

  const arrWhereClause: string[] = [];
  const arrWhereParam: (string | Str_RunHistory_Status)[] = [];
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

  const strWhereClause =
    arrWhereClause.length === 0 ? "" : `WHERE ${arrWhereClause.join(" AND ")}`;

  const arrOrderByClause = options.sortBy.map((dictSort) => {
    if (!Object.hasOwn(MAP_RUN_HISTORY_SORT_COLUMN, dictSort.key)) {
      throw new Error(`Invalid Run History sort key: ${String(dictSort.key)}`);
    }
    if (dictSort.order !== "asc" && dictSort.order !== "desc") {
      throw new Error(`Invalid Run History sort order: ${String(dictSort.order)}`);
    }

    const strColumn = MAP_RUN_HISTORY_SORT_COLUMN[dictSort.key];
    const strOrder = dictSort.order === "asc" ? "ASC" : "DESC";
    return `${strColumn} ${strOrder}`;
  });
  arrOrderByClause.push("run_started_at_ms DESC");
  const strOrderByClause = arrOrderByClause.join(", ");

  const rows = getDatabase()
    .prepare(
      `
      SELECT
          id,
          schedule_name,
          project_name,
          project_version,
          python_environment_name,
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

function parseRetentionLogLocations(
  rows: unknown[],
  sourceName: string,
): Dict_RunHistory_LogLocation[] {
  const arrLogLocation: Dict_RunHistory_LogLocation[] = [];
  for (const [intIndex, row] of rows.entries()) {
    try {
      arrLogLocation.push(
        ensureRunHistoryLogLocationRow(row, `${sourceName}[${intIndex}]`),
      );
    } catch (e: unknown) {
      loggerMain.warn(`Skip invalid Retention log location: ${getErrorMessage(e)}`);
    }
  }
  return arrLogLocation;
}

export function dbSelectLogFolderBefore(cutoffMs: number): Dict_RunHistory_LogLocation[] {
  loggerMain.debug("--dbSelectLogFolderBefore--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          id,
          log_path
      FROM
          run_history
      WHERE
          status <> 'running'
          AND no_log_folder = 0
          AND COALESCE(run_ended_at_ms, run_started_at_ms) < ?
      ORDER BY
          COALESCE(run_ended_at_ms, run_started_at_ms) DESC;
      `,
    )
    .all(cutoffMs);

  return parseRetentionLogLocations(rows, "Expired log folder query result");
}

export function dbSelectVideoBefore(cutoffMs: number): Dict_RunHistory_LogLocation[] {
  loggerMain.debug("--dbSelectVideoBefore--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          id,
          log_path
      FROM
          run_history
      WHERE
          status <> 'running'
          AND no_log_video = 0
          AND COALESCE(run_ended_at_ms, run_started_at_ms) < ?
      ORDER BY
          COALESCE(run_ended_at_ms, run_started_at_ms) DESC;
      `,
    )
    .all(cutoffMs);

  return parseRetentionLogLocations(rows, "Expired video query result");
}

export function dbSelectVideo(): Dict_RunHistory_LogLocation[] {
  loggerMain.debug("--dbSelectVideo--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          id,
          log_path
      FROM
          run_history
      WHERE
          status <> 'running'
          AND no_log_video = 0
      ORDER BY
          COALESCE(run_ended_at_ms, run_started_at_ms) DESC;
      `,
    )
    .all();

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
