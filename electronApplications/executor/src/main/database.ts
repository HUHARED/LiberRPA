// FileName: database.ts
import path from "path";
import fs from "fs";
import Database from "better-sqlite3";
import { strDocumentsFolderPath } from "./commonFunc";
import { loggerMain } from "./logger";
import {
  DictColumns_Project_Detail_DB,
  DictColumns_Project_Detail_ToUpdate,
  DictColumns_Project_Detail_ToInsert,
  DictColumns_Scheduler_ListItem_DB,
  DictColumns_Scheduler_Detail_DB,
  DictColumns_Scheduler_Detail_ToUpdate,
  DictColumns_Scheduler_Detail_ToInsert,
  DictColumns_History_ToInsert,
  DictColumns_History_ToUpdate,
  DictColumns_History_ListItem_DB,
  DictColumns_History_ListItem_Limit_DB,
  Dict_History_Options,
} from "../shared/interface";

const strDatabaseFileFolderPath = path.join(strDocumentsFolderPath, "LiberRPA/AppData");
const strDatabaseFilePath = path.join(strDatabaseFileFolderPath, "ExecutorData.db");
// Ensure the directory structure is created
fs.mkdirSync(strDatabaseFileFolderPath, { recursive: true });
const boolDbExists = fs.existsSync(strDatabaseFilePath);
const db = new Database(strDatabaseFilePath, { verbose: console.log });

const strInitDatabaseScriptPath = path.join(__dirname, "../../resources/InitDatabase.sql");

export function initializeTables(): void {
  loggerMain.debug("--initializeTables--");
  if (boolDbExists) {
    loggerMain.info("Database exists.");
    return;
  }

  loggerMain.info("Create Database.");

  // Create the tables.
  const strTemp = fs.readFileSync(strInitDatabaseScriptPath, { encoding: "utf-8" });
  db.exec(strTemp);
}

/* Project Local Package */

export function dbSelectProjectNames(): { name: string }[] {
  loggerMain.debug("--dbSelectProjectNames--");
  return db
    .prepare("SELECT DISTINCT name FROM project_local ORDER BY updated_at DESC;")
    .all() as { name: string }[];
}

export function dbSelectProjectVersions(name: string): { version: string }[] {
  loggerMain.debug("--dbSelectProjectVersions--");
  return db
    .prepare("SELECT version FROM project_local WHERE name = ? ORDER BY updated_at DESC;")
    .all(name) as { version: string }[];
}

export function dbSelectProjectBindSchedulers(id: number): { name: string }[] {
  loggerMain.debug("--dbSelectProjectBindSchedulers--");
  return db
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
      `
    )
    .all(id) as { name: string }[];
}

export function dbSelectProjectDetail(
  name: string,
  version: string
): DictColumns_Project_Detail_DB {
  loggerMain.debug("--dbSelectProjectDetail--");
  return db
    .prepare("SELECT * FROM project_local WHERE name = ? AND version = ?;")
    .get(name, version) as DictColumns_Project_Detail_DB;
}

export function dbInsertProjectDetail(
  dictDetail: DictColumns_Project_Detail_ToInsert
): Database.RunResult {
  loggerMain.debug("--dbInsertProjectDetail--");
  return db
    .prepare(
      `
      INSERT INTO
          project_local (
              name,
              version,
              description,
              timeout_min,
              buildin_log_level,
              buildin_record_video,
              buildin_stop_shortcut,
              buildin_highlight_ui,
              custom_prj_args
            )
      VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?);
    `
    )
    .run(
      dictDetail.name,
      dictDetail.version,
      dictDetail.description,
      dictDetail.timeout_min,
      dictDetail.buildin_log_level,
      dictDetail.buildin_record_video,
      dictDetail.buildin_stop_shortcut,
      dictDetail.buildin_highlight_ui,
      dictDetail.custom_prj_args
    );
}

export function dbUpdateProjectDetail(
  dictDetail: DictColumns_Project_Detail_ToUpdate
): Database.RunResult {
  loggerMain.debug("--dbUpdateProjectDetail--");
  return db
    .prepare(
      `
      UPDATE project_local
      SET name = ?,
          version = ?,
          description = ?,
          timeout_min = ?,
          buildin_log_level = ?,
          buildin_record_video = ?,
          buildin_stop_shortcut = ?,
          buildin_highlight_ui = ?,
          custom_prj_args = ?
      WHERE id = ?;
      `
    )
    .run(
      dictDetail.name,
      dictDetail.version,
      dictDetail.description,
      dictDetail.timeout_min,
      dictDetail.buildin_log_level,
      dictDetail.buildin_record_video,
      dictDetail.buildin_stop_shortcut,
      dictDetail.buildin_highlight_ui,
      dictDetail.custom_prj_args,
      dictDetail.id
    );
}

export function dbDeleteProject(id: number): Database.RunResult {
  loggerMain.debug("--dbDeleteProject--");
  return db.prepare(`DELETE FROM project_local WHERE id = ?;`).run(id);
}

/* Task Scheduler */

export function dbSelectSchedulerList(): DictColumns_Scheduler_ListItem_DB[] {
  loggerMain.debug("--dbSelectSchedulerList--");
  return db
    .prepare(
      `
      SELECT
          ts.name,
          ts.project_source,
          CASE
              WHEN ts.project_source='local' THEN pl.name
              ELSE 'console'
          END AS project_name,
          CASE
              WHEN ts.project_source='local' THEN pl.version
              ELSE 'console'
          END AS project_version,
          ts.cron,
          ts.enable,
          ts.period_start,
          ts.period_end,
          ts.when_others_running
      FROM
          task_scheduler ts
          LEFT JOIN project_local pl ON ts.project_id = pl.id
      ORDER BY
          ts.updated_at DESC;
      `
    )
    .all() as DictColumns_Scheduler_ListItem_DB[];
}

export function dbSelectSchedulerDetail(name: string): DictColumns_Scheduler_Detail_DB {
  loggerMain.debug("--dbSelectSchedulerDetail--");
  return db
    .prepare(
      `
      SELECT
          ts.id,
          ts.name,
          ts.project_source,
          ts.project_id,
          CASE
              WHEN ts.project_source='local' THEN pl.name
              ELSE 'console'
          END AS project_name,
          CASE
              WHEN ts.project_source='local' THEN pl.version
              ELSE 'console'
          END AS project_version,
          ts.cron,
          ts.when_others_running,
          ts.period_start,
          ts.period_end,
          ts.enable,
          ts.timeout_min,
          ts.buildin_log_level,
          ts.buildin_record_video,
          ts.buildin_stop_shortcut,
          ts.buildin_highlight_ui,
          ts.custom_prj_args,
          ts.created_at,
          ts.updated_at
      FROM
          task_scheduler ts
          LEFT JOIN project_local pl ON ts.project_id=pl.id
      WHERE
          ts.name = ?
      ORDER BY
          ts.updated_at DESC;
      `
    )
    .get(name) as DictColumns_Scheduler_Detail_DB;
}

export function dbInsertSchedulerDetail(
  dictDetail: DictColumns_Scheduler_Detail_ToInsert
): Database.RunResult {
  loggerMain.debug("--dbInsertSchedulerDetail--");
  return db
    .prepare(
      `
      INSERT INTO
          task_scheduler (
              name,
              project_source,
              project_id,
              cron,
              when_others_running,
              period_start,
              period_end,
              enable,
              timeout_min,
              buildin_log_level,
              buildin_record_video,
              buildin_stop_shortcut,
              buildin_highlight_ui,
              custom_prj_args
          )
      VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `
    )
    .run(
      dictDetail.name,
      dictDetail.project_source,
      dictDetail.project_id,
      dictDetail.cron,
      dictDetail.when_others_running,
      dictDetail.period_start,
      dictDetail.period_end,
      dictDetail.enable,
      dictDetail.timeout_min,
      dictDetail.buildin_log_level,
      dictDetail.buildin_record_video,
      dictDetail.buildin_stop_shortcut,
      dictDetail.buildin_highlight_ui,
      dictDetail.custom_prj_args
    );
}

export function dbUpdateSchedulerDetail(
  dictDetail: DictColumns_Scheduler_Detail_ToUpdate
): Database.RunResult {
  loggerMain.debug("--dbUpdateSchedulerDetail--");
  return db
    .prepare(
      `
      UPDATE task_scheduler
      SET
          name=?,
          project_source=?,
          project_id=?,
          cron=?,
          when_others_running=?,
          period_start=?,
          period_end=?,
          enable=?,
          timeout_min=?,
          buildin_log_level=?,
          buildin_record_video=?,
          buildin_stop_shortcut=?,
          buildin_highlight_ui=?,
          custom_prj_args=?
      WHERE
          id = ?
      `
    )
    .run(
      dictDetail.name,
      dictDetail.project_source,
      dictDetail.project_id,
      dictDetail.cron,
      dictDetail.when_others_running,
      dictDetail.period_start,
      dictDetail.period_end,
      dictDetail.enable,
      dictDetail.timeout_min,
      dictDetail.buildin_log_level,
      dictDetail.buildin_record_video,
      dictDetail.buildin_stop_shortcut,
      dictDetail.buildin_highlight_ui,
      dictDetail.custom_prj_args,
      dictDetail.id
    );
}

export function dbDeleteScheduler(id: number): Database.RunResult {
  loggerMain.debug("--dbDeleteScheduler--");
  return db.prepare(`DELETE FROM task_scheduler WHERE id = ?`).run(id);
}

/* Task History */

export function dbInsertHistoryDetail(
  dictDetail: DictColumns_History_ToInsert
): Database.RunResult {
  loggerMain.debug("--dbInsertHistoryDetail--");
  return db
    .prepare(
      `
      INSERT INTO
          task_history (
              scheduler_name,
              project_source,
              project_id,
              project_name,
              project_version,
              run_start,
              status,
              log_path
          )
      VALUES
          (?, ?, ?, ?, ?, ?, ?, ?);
      `
    )
    .run(
      dictDetail.scheduler_name,
      dictDetail.project_source,
      dictDetail.project_id,
      dictDetail.project_name,
      dictDetail.project_version,
      dictDetail.run_start,
      dictDetail.status,
      dictDetail.log_path
    );
}

export function dbUpdateHistoryDetail(
  dictDetail: DictColumns_History_ToUpdate
): Database.RunResult {
  loggerMain.debug("--dbUpdateHistoryDetail--");
  return db
    .prepare(
      `
      UPDATE task_history
      SET
          run_end=?,
          status=?
      WHERE
          id=?;
      `
    )
    .run(dictDetail.run_end, dictDetail.status, dictDetail.id);
}

export function dbUpdateHistoryDetail_unknown(): void {
  // If a Python process exited with Executor, set its values when re-open Executor.
  loggerMain.debug("--dbUpdateHistoryDetail_unknown--");
  db.prepare(
    `
      UPDATE task_history
      SET
          run_end='unknown',
          status='cancel'
      WHERE
          status='running';
      `
  ).run();
}

export function dbSelectCountHistoryRunning(): boolean {
  loggerMain.debug("--dbSelectCountHistoryRunning--");
  const row = db
    .prepare("SELECT COUNT(*) AS runningCount FROM task_history WHERE status = 'running';")
    .get() as { runningCount: number };
  if (row.runningCount > 0) {
    return true;
  } else {
    return false;
  }
}

export function dbSelectLimitHistoryList(
  options: Dict_History_Options
): DictColumns_History_ListItem_Limit_DB {
  loggerMain.debug("--dbSelectLimitHistoryList--");

  const arrWhereClauses: string[] = [];
  const arrParamsWhere: any[] = [];
  if (options.search) {
    if (options.search.scheduler_name && options.search.scheduler_name.trim() !== "") {
      arrWhereClauses.push("scheduler_name LIKE ?");
      arrParamsWhere.push(`%${options.search.scheduler_name.trim()}%`);
    }
    if (options.search.project_source) {
      arrWhereClauses.push("project_source = ?");
      arrParamsWhere.push(options.search.project_source);
    }
    if (options.search.project_name && options.search.project_name.trim() !== "") {
      arrWhereClauses.push("project_name LIKE ?");
      arrParamsWhere.push(`%${options.search.project_name.trim()}%`);
    }
    if (options.search.project_version && options.search.project_version.trim() !== "") {
      arrWhereClauses.push("project_version LIKE ?");
      arrParamsWhere.push(`%${options.search.project_version.trim()}%`);
    }
    if (options.search.status) {
      arrWhereClauses.push("status = ?");
      arrParamsWhere.push(options.search.status);
    }
  }

  const strWhereClause =
    arrWhereClauses.length > 0 ? "WHERE " + arrWhereClauses.join(" AND ") : "";

  let strOrderByClause = "";
  if (options.sortBy.length === 0) {
    strOrderByClause = "run_start DESC";
  } else {
    strOrderByClause =
      options.sortBy
        .map((item) => {
          return item.key + " " + item.order.toUpperCase();
        })
        .join(", ") + ", run_start DESC";
  }

  const rows = db
    .prepare(
      `
      SELECT
          id,
          scheduler_name,
          project_source,
          project_name,
          project_version,
          run_start,
          run_end,
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
      `
    )
    .all(
      ...arrParamsWhere,
      options.itemsPerPage,
      (options.page - 1) * options.itemsPerPage
    ) as DictColumns_History_ListItem_DB[];

  const total = db
    .prepare(
      `
      SELECT
          COUNT(*) as total
      FROM
          task_history
      ${strWhereClause};
      `
    )
    .get(...arrParamsWhere) as {
    total: number;
  };
  return { rows, total: total.total };
}

export function dbSelectProjectNewestVersionDetail(
  name: string
): DictColumns_Project_Detail_DB {
  loggerMain.debug("--dbSelectProjectNewestVersionDetail--");
  return db
    .prepare("SELECT * FROM project_local WHERE name=? ORDER BY created_at DESC;")
    .get(name) as DictColumns_Project_Detail_DB;
}

/* Setting */

export function dbSelect_LogFolder_ByTimeout(timeoutDays: number): string[] {
  loggerMain.debug("--dbSelect_LogFolder_ByTimeout--");
  const rows = db
    .prepare(
      `
      SELECT
          log_path
      FROM
          task_history
      WHERE
          status<>'running'
          AND no_log_folder=FALSE
          AND (
              CASE
                  WHEN run_end<>'unknown' THEN run_end
                  ELSE run_start
              END
          )<datetime ('now', 'localtime', '-'||?||' days')
      ORDER BY
          CASE
              WHEN run_end<>'unknown'
              AND run_end IS NOT NULL THEN run_end
              ELSE run_start
          END DESC;
      `
    )
    .all(timeoutDays) as { log_path: string }[];

  return rows.map((row) => row.log_path);
}

export function dbSelect_Video_ByTimeout(timeoutDays: number): string[] {
  loggerMain.debug("--dbSelect_Video_ByTimeout--");
  const rows = db
    .prepare(
      `
      SELECT
          log_path
      FROM
          task_history
      WHERE
          status<>'running'
          AND no_log_video=FALSE
          AND (
              CASE
                  WHEN run_end<>'unknown' THEN run_end
                  ELSE run_start
              END
          )<datetime ('now', 'localtime', '-'||?||' days')
      ORDER BY
          CASE
              WHEN run_end<>'unknown'
              AND run_end IS NOT NULL THEN run_end
              ELSE run_start
          END DESC;
      `
    )
    .all(timeoutDays) as { log_path: string }[];

  return rows.map((row) => row.log_path);
}

export function dbSelect_Video(): string[] {
  loggerMain.debug("--dbSelect_Video--");
  const rows = db
    .prepare(
      `
      SELECT
          log_path
      FROM
          task_history
      WHERE
          status<>'running'
          AND no_log_video=FALSE
      ORDER BY
          CASE
              WHEN run_end<>'unknown'
              AND run_end IS NOT NULL THEN run_end
              ELSE run_start
          END DESC;
      `
    )
    .all() as { log_path: string }[];

  return rows.map((row) => row.log_path);
}

export function dbUpdate_NoLogFolderAndVideo(log_path: string): void {
  loggerMain.debug("--dbUpdate_NoLogFolderAndVideo--");
  db.prepare(
    `
      UPDATE task_history
      SET
          no_log_folder=TRUE,
          no_log_video=TRUE
      WHERE
          log_path=?;
      `
  ).run(log_path);
}

export function dbUpdate_NoVideo(log_path: string): void {
  loggerMain.debug("--dbUpdate_NoVideo--");
  db.prepare(
    `
      UPDATE task_history
      SET
          no_log_video=TRUE
      WHERE
          log_path=?;
      `
  ).run(log_path);
}
