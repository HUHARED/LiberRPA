// FileName: scheduleRepository.ts

import type { Dict_ProjectRun_Detail } from "../Run/types";
import type {
  Dict_ScheduleCreate,
  Dict_Detail_Schedule,
  Dict_ListItem_Schedule,
  Dict_ScheduleUpdate,
} from "../../shared/schedule";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  ensureScheduleDetailRow,
  ensureScheduleListRows,
  ensureScheduleRunDetailRow,
  ensureSingleRowAffected,
} from "./rowValidation";

export function dbSelectScheduleList(): Dict_ListItem_Schedule[] {
  loggerMain.debug("--dbSelectScheduleList--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          s.id,
          s.name,
          p.name AS project_name,
          p.version AS project_version,
          s.cron,
          s.enable,
          s.period_start_ms,
          s.period_end_ms,
          s.run_conflict_policy
      FROM
          schedule s
          INNER JOIN project p ON s.project_id = p.id
      ORDER BY
          s.updated_at_ms DESC;
      `,
    )
    .all();
  return ensureScheduleListRows(rows, "Schedule list query result");
}

export function dbSelectScheduleDetail(name: string): Dict_Detail_Schedule | undefined {
  loggerMain.debug("--dbSelectScheduleDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          s.id,
          s.name,
          s.project_id,
          p.name AS project_name,
          p.version AS project_version,
          s.cron,
          s.run_conflict_policy,
          s.period_start_ms,
          s.period_end_ms,
          s.enable,
          s.timeout_min,
          s.builtin_log_level,
          s.builtin_record_video,
          s.builtin_stop_shortcut,
          s.builtin_highlight_ui,
          s.custom_prj_args,
          s.created_at_ms,
          s.updated_at_ms
      FROM
          schedule s
          INNER JOIN project p ON s.project_id = p.id
      WHERE
          s.name = ?;
      `,
    )
    .get(name);
  return row === undefined
    ? undefined
    : ensureScheduleDetailRow(row, "Schedule detail query result");
}

export function dbSelectScheduleRunDetail(
  scheduleId: number,
): Dict_ProjectRun_Detail | undefined {
  loggerMain.debug("--dbSelectScheduleRunDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          s.name AS schedule_name,
          s.project_id AS id,
          p.name AS name,
          p.version AS version,
          p.python_environment_name,
          s.timeout_min,
          s.builtin_log_level,
          s.builtin_record_video,
          s.builtin_stop_shortcut,
          s.builtin_highlight_ui,
          s.custom_prj_args
      FROM
          schedule s
          INNER JOIN project p ON s.project_id = p.id
      WHERE
          s.id = ?;
      `,
    )
    .get(scheduleId);
  return row === undefined
    ? undefined
    : ensureScheduleRunDetailRow(row, "Schedule Run detail query result");
}

export function dbInsertSchedule(detailDict: Dict_ScheduleCreate): void {
  loggerMain.debug("--dbInsertSchedule--");
  const intNowMs = Date.now();
  const result = getDatabase()
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
      detailDict.name,
      detailDict.project_id,
      detailDict.cron,
      detailDict.run_conflict_policy,
      detailDict.period_start_ms,
      detailDict.period_end_ms,
      detailDict.enable ? 1 : 0,
      detailDict.timeout_min,
      detailDict.builtin_log_level,
      detailDict.builtin_record_video ? 1 : 0,
      detailDict.builtin_stop_shortcut ? 1 : 0,
      detailDict.builtin_highlight_ui ? 1 : 0,
      JSON.stringify(detailDict.custom_prj_args),
      intNowMs,
      intNowMs,
    );
  ensureSingleRowAffected(result, `Insert Schedule '${detailDict.name}'`);
}

export function dbUpdateSchedule(detailDict: Dict_ScheduleUpdate): void {
  loggerMain.debug("--dbUpdateSchedule--");
  const result = getDatabase()
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
      detailDict.name,
      detailDict.project_id,
      detailDict.cron,
      detailDict.run_conflict_policy,
      detailDict.period_start_ms,
      detailDict.period_end_ms,
      detailDict.enable ? 1 : 0,
      detailDict.timeout_min,
      detailDict.builtin_log_level,
      detailDict.builtin_record_video ? 1 : 0,
      detailDict.builtin_stop_shortcut ? 1 : 0,
      detailDict.builtin_highlight_ui ? 1 : 0,
      JSON.stringify(detailDict.custom_prj_args),
      Date.now(),
      detailDict.id,
    );
  ensureSingleRowAffected(result, `Update Schedule ID ${detailDict.id}`);
}

export function dbDeleteSchedule(id: number): void {
  loggerMain.debug("--dbDeleteSchedule--");
  const result = getDatabase().prepare("DELETE FROM schedule WHERE id = ?;").run(id);
  ensureSingleRowAffected(result, `Delete Schedule ID ${id}`);
}
