// FileName: database.ts

import Database from "better-sqlite3";
import fs from "fs";
import path from "path";

import { strDocumentsFolderPath } from "./commonFunc";
import { loggerMain } from "./logger";
import {
  ensureCountRow,
  ensureHistoryListRows,
  ensureLogPathRows,
  ensureNameRows,
  ensureProjectDetailRow,
  ensureSchedulerDetailRow,
  ensureSchedulerListRows,
  ensureVersionRows,
} from "./databaseValidation";
import type {
  DictColumns_History_ListItem_Limit_DB,
  DictColumns_History_ToInsert,
  DictColumns_History_ToUpdate,
  DictColumns_Project_Detail_DB,
  DictColumns_Project_Detail_ToInsert,
  DictColumns_Project_Detail_ToUpdate,
  DictColumns_Scheduler_Detail_DB,
  DictColumns_Scheduler_Detail_ToInsert,
  DictColumns_Scheduler_Detail_ToUpdate,
  DictColumns_Scheduler_ListItem_DB,
  Dict_History_Options,
} from "../shared/interface";

const INT_DATABASE_SCHEMA_VERSION = 2;
const STR_DATABASE_FOLDER_PATH = path.join(strDocumentsFolderPath, "LiberRPA/AppData");
const STR_DATABASE_FILE_PATH = path.join(STR_DATABASE_FOLDER_PATH, "ExecutorData.db");
const STR_INIT_DATABASE_SCRIPT_PATH = path.join(
  __dirname,
  "../../resources/InitDatabase.sql",
);

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

let databaseObj: Database.Database | undefined;

export function initializeDatabase(): void {
  loggerMain.debug("--initializeDatabase--");
  fs.mkdirSync(STR_DATABASE_FOLDER_PATH, { recursive: true });

  if (!fs.existsSync(STR_DATABASE_FILE_PATH)) {
    databaseObj = createDatabase();
    return;
  }

  const existingDatabaseObj = openDatabase(STR_DATABASE_FILE_PATH);
  const intSchemaVersion = getDatabaseSchemaVersionOrClose(existingDatabaseObj);

  if (intSchemaVersion === INT_DATABASE_SCHEMA_VERSION) {
    databaseObj = existingDatabaseObj;
    loggerMain.info(`Opened Executor database schema ${intSchemaVersion}.`);
    return;
  }

  existingDatabaseObj.close();
  const strBackupPath = backupDatabaseFiles();
  loggerMain.warn(
    `Backed up Executor database schema ${intSchemaVersion} to ${strBackupPath}.`,
  );
  databaseObj = createDatabase();
}

export function closeDatabase(): void {
  if (databaseObj === undefined) {
    return;
  }

  databaseObj.close();
  databaseObj = undefined;
}

function openDatabase(strDatabasePath: string): Database.Database {
  const openedDatabaseObj = new Database(strDatabasePath, {
    verbose: (message?: unknown) => {
      loggerMain.debug(`[SQLite] ${String(message)}`);
    },
  });
  openedDatabaseObj.pragma("foreign_keys = ON");
  return openedDatabaseObj;
}

function createDatabase(): Database.Database {
  loggerMain.info("Create Executor database.");
  const newDatabaseObj = openDatabase(STR_DATABASE_FILE_PATH);

  try {
    const strInitScript = fs.readFileSync(STR_INIT_DATABASE_SCRIPT_PATH, {
      encoding: "utf-8",
    });
    newDatabaseObj.exec(strInitScript);

    const intSchemaVersion = getDatabaseSchemaVersion(newDatabaseObj);
    if (intSchemaVersion !== INT_DATABASE_SCHEMA_VERSION) {
      throw new Error(
        `The initialized database schema is ${intSchemaVersion}, expected ${INT_DATABASE_SCHEMA_VERSION}.`,
      );
    }

    return newDatabaseObj;
  } catch (e: unknown) {
    newDatabaseObj.close();
    removeDatabaseFiles(STR_DATABASE_FILE_PATH);
    throw e;
  }
}

function getDatabaseSchemaVersionOrClose(targetDatabaseObj: Database.Database): number {
  try {
    return getDatabaseSchemaVersion(targetDatabaseObj);
  } catch (e: unknown) {
    targetDatabaseObj.close();
    throw e;
  }
}

function getDatabaseSchemaVersion(targetDatabaseObj: Database.Database): number {
  const value = targetDatabaseObj.pragma("user_version", { simple: true });
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error(`Invalid Executor database schema version: ${String(value)}`);
  }
  return value;
}

function backupDatabaseFiles(): string {
  const strTimestamp = new Date().toISOString().replace(/[-:.]/g, "");
  const strBackupPath = path.join(
    STR_DATABASE_FOLDER_PATH,
    `ExecutorData.backup.${strTimestamp}.db`,
  );

  for (const strSuffix of ["", "-wal", "-shm", "-journal"]) {
    const strSourcePath = STR_DATABASE_FILE_PATH + strSuffix;
    if (fs.existsSync(strSourcePath)) {
      fs.renameSync(strSourcePath, strBackupPath + strSuffix);
    }
  }

  return strBackupPath;
}

function removeDatabaseFiles(strDatabasePath: string): void {
  for (const strSuffix of ["", "-wal", "-shm", "-journal"]) {
    fs.rmSync(strDatabasePath + strSuffix, { force: true });
  }
}

function getDatabase(): Database.Database {
  if (databaseObj === undefined) {
    throw new Error("Executor database has not been initialized.");
  }
  return databaseObj;
}

/* Project Local Package */

export function dbSelectProjectNames(): { name: string }[] {
  loggerMain.debug("--dbSelectProjectNames--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          name
      FROM
          project_local
      GROUP BY
          name
      ORDER BY
          MAX(updated_at_ms) DESC;
      `,
    )
    .all();
  return ensureNameRows(rows, "Project name query result");
}

export function dbSelectProjectVersions(name: string): { version: string }[] {
  loggerMain.debug("--dbSelectProjectVersions--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          version
      FROM
          project_local
      WHERE
          name = ?
      ORDER BY
          updated_at_ms DESC;
      `,
    )
    .all(name);
  return ensureVersionRows(rows, "Project version query result");
}

export function dbSelectProjectBindSchedulers(id: number): { name: string }[] {
  loggerMain.debug("--dbSelectProjectBindSchedulers--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          name
      FROM
          task_scheduler
      WHERE
          project_id = ?
      ORDER BY
          name ASC;
      `,
    )
    .all(id);
  return ensureNameRows(rows, "Bound Schedule query result");
}

export function dbSelectProjectDetail(
  name: string,
  version: string,
): DictColumns_Project_Detail_DB | undefined {
  loggerMain.debug("--dbSelectProjectDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          name,
          version,
          description,
          version_summary,
          python_environment_name,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          project_local
      WHERE
          name = ?
          AND version = ?;
      `,
    )
    .get(name, version);
  return row === undefined
    ? undefined
    : ensureProjectDetailRow(row, "Project detail query result");
}

export function dbInsertProjectDetail(
  dictDetail: DictColumns_Project_Detail_ToInsert,
): Database.RunResult {
  loggerMain.debug("--dbInsertProjectDetail--");
  const intNowMs = Date.now();
  return getDatabase()
    .prepare(
      `
      INSERT INTO
          project_local (
              name,
              version,
              description,
              version_summary,
              python_environment_name,
              timeout_min,
              builtin_log_level,
              builtin_record_video,
              builtin_stop_shortcut,
              builtin_highlight_ui,
              custom_prj_args,
              created_at_ms,
              updated_at_ms
          )
      VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
      dictDetail.name,
      dictDetail.version,
      dictDetail.description,
      dictDetail.version_summary ?? "",
      dictDetail.python_environment_name,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video,
      dictDetail.builtin_stop_shortcut,
      dictDetail.builtin_highlight_ui,
      dictDetail.custom_prj_args,
      intNowMs,
      intNowMs,
    );
}

export function dbUpdateProjectDetail(
  dictDetail: DictColumns_Project_Detail_ToUpdate,
): Database.RunResult {
  loggerMain.debug("--dbUpdateProjectDetail--");
  return getDatabase()
    .prepare(
      `
      UPDATE project_local
      SET
          name = ?,
          version = ?,
          description = ?,
          version_summary = ?,
          python_environment_name = ?,
          timeout_min = ?,
          builtin_log_level = ?,
          builtin_record_video = ?,
          builtin_stop_shortcut = ?,
          builtin_highlight_ui = ?,
          custom_prj_args = ?,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(
      dictDetail.name,
      dictDetail.version,
      dictDetail.description,
      dictDetail.version_summary,
      dictDetail.python_environment_name,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video,
      dictDetail.builtin_stop_shortcut,
      dictDetail.builtin_highlight_ui,
      dictDetail.custom_prj_args,
      Date.now(),
      dictDetail.id,
    );
}

export function dbDeleteProject(id: number): Database.RunResult {
  loggerMain.debug("--dbDeleteProject--");

  const arrBoundScheduler = dbSelectProjectBindSchedulers(id);
  if (arrBoundScheduler.length !== 0) {
    throw new Error(
      `Cannot delete Project ${id} because it is used by Scheduler: ${arrBoundScheduler
        .map((dictScheduler) => dictScheduler.name)
        .join(", ")}.`,
    );
  }

  return getDatabase().prepare("DELETE FROM project_local WHERE id = ?;").run(id);
}

/* Task Scheduler */

export function dbSelectSchedulerList(): DictColumns_Scheduler_ListItem_DB[] {
  loggerMain.debug("--dbSelectSchedulerList--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          ts.name,
          ts.project_source,
          CASE
              WHEN ts.project_source = 'local' THEN pl.name
              ELSE 'console'
          END AS project_name,
          CASE
              WHEN ts.project_source = 'local' THEN pl.version
              ELSE 'console'
          END AS project_version,
          ts.cron,
          ts.enable,
          ts.period_start_ms,
          ts.period_end_ms,
          ts.when_others_running
      FROM
          task_scheduler ts
          LEFT JOIN project_local pl ON ts.project_id = pl.id
      ORDER BY
          ts.updated_at_ms DESC;
      `,
    )
    .all();
  return ensureSchedulerListRows(rows, "Schedule list query result");
}

export function dbSelectSchedulerDetail(
  name: string,
): DictColumns_Scheduler_Detail_DB | undefined {
  loggerMain.debug("--dbSelectSchedulerDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          ts.id,
          ts.name,
          ts.project_source,
          ts.project_id,
          CASE
              WHEN ts.project_source = 'local' THEN pl.name
              ELSE 'console'
          END AS project_name,
          CASE
              WHEN ts.project_source = 'local' THEN pl.version
              ELSE 'console'
          END AS project_version,
          CASE
              WHEN ts.project_source = 'local' THEN pl.python_environment_name
              ELSE 'default'
          END AS python_environment_name,
          ts.cron,
          ts.when_others_running,
          ts.period_start_ms,
          ts.period_end_ms,
          ts.enable,
          ts.timeout_min,
          ts.builtin_log_level,
          ts.builtin_record_video,
          ts.builtin_stop_shortcut,
          ts.builtin_highlight_ui,
          ts.custom_prj_args,
          ts.created_at_ms,
          ts.updated_at_ms
      FROM
          task_scheduler ts
          LEFT JOIN project_local pl ON ts.project_id = pl.id
      WHERE
          ts.name = ?;
      `,
    )
    .get(name);
  return row === undefined
    ? undefined
    : ensureSchedulerDetailRow(row, "Schedule detail query result");
}

export function dbInsertSchedulerDetail(
  dictDetail: DictColumns_Scheduler_Detail_ToInsert,
): Database.RunResult {
  loggerMain.debug("--dbInsertSchedulerDetail--");
  const intNowMs = Date.now();
  return getDatabase()
    .prepare(
      `
      INSERT INTO
          task_scheduler (
              name,
              project_source,
              project_id,
              cron,
              when_others_running,
              period_start_ms,
              period_end_ms,
              enable,
              timeout_min,
              builtin_log_level,
              builtin_record_video,
              builtin_stop_shortcut,
              builtin_highlight_ui,
              custom_prj_args,
              created_at_ms,
              updated_at_ms
          )
      VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
      dictDetail.name,
      dictDetail.project_source,
      dictDetail.project_id,
      dictDetail.cron,
      dictDetail.when_others_running,
      dictDetail.period_start_ms,
      dictDetail.period_end_ms,
      dictDetail.enable,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video,
      dictDetail.builtin_stop_shortcut,
      dictDetail.builtin_highlight_ui,
      dictDetail.custom_prj_args,
      intNowMs,
      intNowMs,
    );
}

export function dbUpdateSchedulerDetail(
  dictDetail: DictColumns_Scheduler_Detail_ToUpdate,
): Database.RunResult {
  loggerMain.debug("--dbUpdateSchedulerDetail--");
  return getDatabase()
    .prepare(
      `
      UPDATE task_scheduler
      SET
          name = ?,
          project_source = ?,
          project_id = ?,
          cron = ?,
          when_others_running = ?,
          period_start_ms = ?,
          period_end_ms = ?,
          enable = ?,
          timeout_min = ?,
          builtin_log_level = ?,
          builtin_record_video = ?,
          builtin_stop_shortcut = ?,
          builtin_highlight_ui = ?,
          custom_prj_args = ?,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(
      dictDetail.name,
      dictDetail.project_source,
      dictDetail.project_id,
      dictDetail.cron,
      dictDetail.when_others_running,
      dictDetail.period_start_ms,
      dictDetail.period_end_ms,
      dictDetail.enable,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video,
      dictDetail.builtin_stop_shortcut,
      dictDetail.builtin_highlight_ui,
      dictDetail.custom_prj_args,
      Date.now(),
      dictDetail.id,
    );
}

export function dbDeleteScheduler(id: number): Database.RunResult {
  loggerMain.debug("--dbDeleteScheduler--");
  return getDatabase().prepare("DELETE FROM task_scheduler WHERE id = ?;").run(id);
}

/* Task History */

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

export function dbSelectProjectNewestVersionDetail(
  name: string,
): DictColumns_Project_Detail_DB | undefined {
  loggerMain.debug("--dbSelectProjectNewestVersionDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          name,
          version,
          description,
          version_summary,
          python_environment_name,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          project_local
      WHERE
          name = ?
      ORDER BY
          created_at_ms DESC
      LIMIT
          1;
      `,
    )
    .get(name);
  return row === undefined
    ? undefined
    : ensureProjectDetailRow(row, "Newest Project version query result");
}

/* Setting */

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
