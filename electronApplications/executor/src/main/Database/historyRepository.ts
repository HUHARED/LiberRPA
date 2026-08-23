import type Database from "better-sqlite3";

import type {
  DictColumns_History_ListItem_Limit_DB,
  DictColumns_History_ToInsert,
  DictColumns_History_ToUpdate,
  Dict_History_Options,
} from "../../shared/interface";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import { ensureCountRow, ensureHistoryListRows, ensureLogPathRows } from "./rowValidation";

const MAP_HISTORY_SORT_COLUMN: Record<
  Dict_History_Options["sortBy"][number]["key"],
  string
> = {
  scheduler_name: "scheduler_name",
  project_source: "project_source",
  project_name: "project_name",
  project_version: "project_version",
  python_environment_name: "python_environment_name",
  run_started_at_ms: "run_started_at_ms",
  run_ended_at_ms: "run_ended_at_ms",
  status: "status",
};

export function dbInsertHistoryDetail(
  dictDetail: DictColumns_History_ToInsert,
): Database.RunResult {
  loggerMain.debug("--dbInsertHistoryDetail--");
  const intNowMs = Date.now();
  return getDatabase()
    .prepare(
      `
      INSERT INTO
          task_history (
              scheduler_name,
              project_source,
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
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
      dictDetail.scheduler_name,
      dictDetail.project_source,
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

export function dbUpdateHistoryDetail(
  dictDetail: DictColumns_History_ToUpdate,
): Database.RunResult {
  loggerMain.debug("--dbUpdateHistoryDetail--");
  return getDatabase()
    .prepare(
      `
      UPDATE task_history
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

export function dbMarkRunningHistoryInterrupted(): void {
  loggerMain.debug("--dbMarkRunningHistoryInterrupted--");
  const result = getDatabase()
    .prepare(
      `
      UPDATE task_history
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
    loggerMain.warn(`Marked ${result.changes} unfinished task(s) as interrupted.`);
  }
}

export function dbSelectCountHistoryRunning(): boolean {
  loggerMain.debug("--dbSelectCountHistoryRunning--");
  const row = getDatabase()
    .prepare("SELECT COUNT(*) AS runningCount FROM task_history WHERE status = 'running';")
    .get();
  return ensureCountRow(row, "runningCount", "Running History count query result") > 0;
}

export function dbSelectLimitHistoryList(
  options: Dict_History_Options,
): DictColumns_History_ListItem_Limit_DB {
  loggerMain.debug("--dbSelectLimitHistoryList--");

  if (!Number.isSafeInteger(options.page) || options.page < 1) {
    throw new Error(`Invalid Task History page: ${String(options.page)}`);
  }
  if (!Number.isSafeInteger(options.itemsPerPage) || options.itemsPerPage < 1) {
    throw new Error(`Invalid Task History itemsPerPage: ${String(options.itemsPerPage)}`);
  }
  if (!Array.isArray(options.sortBy)) {
    throw new Error("Task History sortBy must be an array.");
  }

  const arrWhereClause: string[] = [];
  const arrWhereParam: string[] = [];
  if (options.search.scheduler_name.trim() !== "") {
    arrWhereClause.push("scheduler_name LIKE ?");
    arrWhereParam.push(`%${options.search.scheduler_name.trim()}%`);
  }
  if (options.search.project_source !== null) {
    arrWhereClause.push("project_source = ?");
    arrWhereParam.push(options.search.project_source);
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
    if (!Object.hasOwn(MAP_HISTORY_SORT_COLUMN, dictSort.key)) {
      throw new Error(`Invalid Task History sort key: ${String(dictSort.key)}`);
    }
    if (dictSort.order !== "asc" && dictSort.order !== "desc") {
      throw new Error(`Invalid Task History sort order: ${String(dictSort.order)}`);
    }

    const strColumn = MAP_HISTORY_SORT_COLUMN[dictSort.key];
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
          scheduler_name,
          project_source,
          project_name,
          project_version,
          python_environment_name,
          run_started_at_ms,
          run_ended_at_ms,
          status,
          log_path
      FROM
          task_history
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
  const arrRow = ensureHistoryListRows(rows, "Run History query result");

  const total = getDatabase()
    .prepare(
      `
      SELECT
          COUNT(*) AS total
      FROM
          task_history
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
          task_history
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
          task_history
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
          task_history
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
      UPDATE task_history
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
      UPDATE task_history
      SET
          no_log_video = 1,
          updated_at_ms = ?
      WHERE
          log_path = ?;
      `,
    )
    .run(Date.now(), strLogPath);
}
