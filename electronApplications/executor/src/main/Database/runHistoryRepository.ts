import type Database from "better-sqlite3";

import type {
  DictRunHistoryOptions,
  DictRunHistoryPage,
  TypeRunHistoryStatus,
} from "../../shared/run";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  ensureCountRow,
  ensureLogPathRow,
  ensureLogPathRows,
  ensureRunHistoryListRows,
} from "./rowValidation";

interface DictRunHistoryInsert {
  schedule_name: string | null;
  project_id: number;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  status: "running";
  log_path: string;
}

type DictRunHistoryUpdate =
  | {
      id: number;
      run_ended_at_ms: number;
      status: "completed" | "error" | "cancel" | "timeout";
    }
  | {
      id: number;
      run_ended_at_ms: null;
      status: "interrupted";
    };

const MAP_RUN_HISTORY_SORT_COLUMN: Record<
  DictRunHistoryOptions["sortBy"][number]["key"],
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

export function dbInsertRunHistory(dictDetail: DictRunHistoryInsert): Database.RunResult {
  loggerMain.debug("--dbInsertRunHistory--");
  const intNowMs = Date.now();
  return getDatabase()
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
      dictDetail.schedule_name,
      dictDetail.project_id,
      dictDetail.project_name,
      dictDetail.project_version,
      dictDetail.python_environment_name,
      dictDetail.run_started_at_ms,
      dictDetail.status,
      dictDetail.log_path,
      intNowMs,
      intNowMs,
    );
}

export function dbUpdateRunHistory(dictDetail: DictRunHistoryUpdate): Database.RunResult {
  loggerMain.debug("--dbUpdateRunHistory--");
  return getDatabase()
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
    .run(dictDetail.run_ended_at_ms, dictDetail.status, Date.now(), dictDetail.id);
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
  loggerMain.debug("--dbHasRunningRun--");
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

export function dbSelectRunHistoryLogPath(id: number): string | undefined {
  loggerMain.debug("--dbSelectRunHistoryLogPath--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
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
    : ensureLogPathRow(row, "Run History log path query result");
}

export function dbSelectRunHistoryPage(options: DictRunHistoryOptions): DictRunHistoryPage {
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
  const arrWhereParam: (string | TypeRunHistoryStatus)[] = [];
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

export function dbSelectLogFolderBefore(intCutoffMs: number): string[] {
  loggerMain.debug("--dbSelectLogFolderBefore--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
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
    .all(intCutoffMs);

  return ensureLogPathRows(rows, "Expired log folder query result");
}

export function dbSelectVideoBefore(intCutoffMs: number): string[] {
  loggerMain.debug("--dbSelectVideoBefore--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
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
    .all(intCutoffMs);

  return ensureLogPathRows(rows, "Expired video query result");
}

export function dbSelectVideo(): string[] {
  loggerMain.debug("--dbSelectVideo--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
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

  return ensureLogPathRows(rows, "Video query result");
}

export function dbUpdateNoLogFolderAndVideo(strLogPath: string): void {
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
          log_path = ?;
      `,
    )
    .run(Date.now(), strLogPath);
}

export function dbUpdateNoVideo(strLogPath: string): void {
  loggerMain.debug("--dbUpdateNoVideo--");
  getDatabase()
    .prepare(
      `
      UPDATE run_history
      SET
          no_log_video = 1,
          updated_at_ms = ?
      WHERE
          log_path = ?;
      `,
    )
    .run(Date.now(), strLogPath);
}
