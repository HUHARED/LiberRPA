import type Database from "better-sqlite3";

import type {
  DictColumns_Scheduler_Detail_DB,
  DictColumns_Scheduler_Detail_ToInsert,
  DictColumns_Scheduler_Detail_ToUpdate,
  DictColumns_Scheduler_ListItem_DB,
} from "../../shared/interface";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import { ensureSchedulerDetailRow, ensureSchedulerListRows } from "./rowValidation";

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
