// FileName: scheduleRepository.ts

import type { ProjectRunConfig } from "../Run/types";
import type {
  ScheduleCreateData,
  ScheduleDetails,
  ScheduleListItem,
  ScheduleUpdateData,
} from "../../shared/schedule";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  ensureScheduleDetailRow,
  ensureScheduleListRows,
  ensureScheduleRunDetailRow,
  ensureSingleRowAffected,
} from "./rowValidation";

export function dbSelectScheduleList(): ScheduleListItem[] {
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
          s.enabled,
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

export function dbSelectScheduleDetail(name: string): ScheduleDetails | undefined {
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
          s.enabled,
          s.max_retry_count,
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
): ProjectRunConfig | undefined {
  loggerMain.debug("--dbSelectScheduleRunDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          s.name AS schedule_name,
          s.run_conflict_policy,
          s.project_id AS local_project_id,
          p.name AS project_name,
          p.version AS project_version,
          p.python_environment_name,
          s.max_retry_count,
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

export function dbInsertSchedule(detailDict: ScheduleCreateData): void {
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
              enabled,
              max_retry_count,
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
      detailDict.name,
      detailDict.project_id,
      detailDict.cron,
      detailDict.run_conflict_policy,
      detailDict.period_start_ms,
      detailDict.period_end_ms,
      detailDict.enabled ? 1 : 0,
      detailDict.max_retry_count,
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

export function dbUpdateSchedule(detailDict: ScheduleUpdateData): void {
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
          enabled = ?,
          max_retry_count = ?,
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
      detailDict.enabled ? 1 : 0,
      detailDict.max_retry_count,
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

export function dbSetScheduleEnabled(id: number, enabled: boolean): void {
  const result = getDatabase()
    .prepare(
      `
      UPDATE schedule
      SET
          enabled = ?,
          updated_at_ms = ?
      WHERE
          id = ?
      `,
    )
    .run(enabled ? 1 : 0, Date.now(), id);
  ensureSingleRowAffected(result, `Set Schedule ${id} enabled`);
}
