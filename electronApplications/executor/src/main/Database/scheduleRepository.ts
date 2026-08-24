import type Database from "better-sqlite3";

import type { DictProjectRunDetail } from "../Run/types";
import type {
  DictScheduleCreate,
  DictScheduleDetail,
  DictScheduleListItem,
  DictScheduleUpdate,
} from "../../shared/schedule";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  ensureScheduleDetailRow,
  ensureScheduleListRows,
  ensureScheduleRunDetailRow,
} from "./rowValidation";

export function dbSelectScheduleList(): DictScheduleListItem[] {
  loggerMain.debug("--dbSelectScheduleList--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          ts.name,
          pl.name AS project_name,
          pl.version AS project_version,
          ts.cron,
          ts.enable,
          ts.period_start_ms,
          ts.period_end_ms,
          ts.run_conflict_policy
      FROM
          schedule ts
          INNER JOIN project pl ON ts.project_id = pl.id
      ORDER BY
          ts.updated_at_ms DESC;
      `,
    )
    .all();
  return ensureScheduleListRows(rows, "Schedule list query result");
}

export function dbSelectScheduleDetail(name: string): DictScheduleDetail | undefined {
  loggerMain.debug("--dbSelectScheduleDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          ts.id,
          ts.name,
          ts.project_id,
          pl.name AS project_name,
          pl.version AS project_version,
          ts.cron,
          ts.run_conflict_policy,
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
          schedule ts
          INNER JOIN project pl ON ts.project_id = pl.id
      WHERE
          ts.name = ?;
      `,
    )
    .get(name);
  return row === undefined
    ? undefined
    : ensureScheduleDetailRow(row, "Schedule detail query result");
}

export function dbSelectScheduleRunDetail(name: string): DictProjectRunDetail | undefined {
  loggerMain.debug("--dbSelectScheduleRunDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          ts.name AS schedule_name,
          ts.project_id AS id,
          pl.name AS name,
          pl.version AS version,
          pl.python_environment_name,
          ts.timeout_min,
          ts.builtin_log_level,
          ts.builtin_record_video,
          ts.builtin_stop_shortcut,
          ts.builtin_highlight_ui,
          ts.custom_prj_args
      FROM
          schedule ts
          INNER JOIN project pl ON ts.project_id = pl.id
      WHERE
          ts.name = ?;
      `,
    )
    .get(name);
  return row === undefined
    ? undefined
    : ensureScheduleRunDetailRow(row, "Schedule Run detail query result");
}

export function dbInsertSchedule(dictDetail: DictScheduleCreate): Database.RunResult {
  loggerMain.debug("--dbInsertSchedule--");
  const intNowMs = Date.now();
  return getDatabase()
    .prepare(
      `
      INSERT INTO
          schedule (
              name,
              project_id,
              cron,
              run_conflict_policy,
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
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
      dictDetail.name,
      dictDetail.project_id,
      dictDetail.cron,
      dictDetail.run_conflict_policy,
      dictDetail.period_start_ms,
      dictDetail.period_end_ms,
      dictDetail.enable ? 1 : 0,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video ? 1 : 0,
      dictDetail.builtin_stop_shortcut ? 1 : 0,
      dictDetail.builtin_highlight_ui ? 1 : 0,
      JSON.stringify(dictDetail.custom_prj_args),
      intNowMs,
      intNowMs,
    );
}

export function dbUpdateSchedule(dictDetail: DictScheduleUpdate): Database.RunResult {
  loggerMain.debug("--dbUpdateSchedule--");
  return getDatabase()
    .prepare(
      `
      UPDATE schedule
      SET
          name = ?,
          project_id = ?,
          cron = ?,
          run_conflict_policy = ?,
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
      dictDetail.project_id,
      dictDetail.cron,
      dictDetail.run_conflict_policy,
      dictDetail.period_start_ms,
      dictDetail.period_end_ms,
      dictDetail.enable ? 1 : 0,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video ? 1 : 0,
      dictDetail.builtin_stop_shortcut ? 1 : 0,
      dictDetail.builtin_highlight_ui ? 1 : 0,
      JSON.stringify(dictDetail.custom_prj_args),
      Date.now(),
      dictDetail.id,
    );
}

export function dbDeleteSchedule(id: number): Database.RunResult {
  loggerMain.debug("--dbDeleteSchedule--");
  return getDatabase().prepare("DELETE FROM schedule WHERE id = ?;").run(id);
}
