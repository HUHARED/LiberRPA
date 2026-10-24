// FileName: scheduleRepository.ts

import type { RunConfig } from "../../shared/run";
import type {
  ScheduleListItem,
  ScheduleDetails,
  ScheduleCreateData,
  ScheduleUpdateData,
} from "../../shared/schedule";
import type { RunSettings } from "../../shared/runSettings";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  type RunSettingsRow,
  convertRunSettingsRow,
  ensureSingleRowAffected,
} from "./rowConversion";

type ScheduleListItemRow = Omit<ScheduleListItem, "enabled"> & { enabled: 0 | 1 };
type ScheduleDetailsRow = Omit<ScheduleDetails, keyof RunSettings | "enabled"> &
  RunSettingsRow & { enabled: 0 | 1 };
type ScheduleRunConfigRow = Omit<RunConfig, keyof RunSettings> & RunSettingsRow;

export function dbSelectScheduleList(): ScheduleListItem[] {
  loggerMain.debug("--dbSelectScheduleList--");
  const rows = getDatabase()
    .prepare<[], ScheduleListItemRow>(
      `
      SELECT
          s.id,
          s.name,
          p.project_name,
          p.project_version,
          s.cron,
          s.enabled,
          s.period_start_ms,
          s.period_end_ms,
          s.run_conflict_policy
      FROM
          schedule s
          INNER JOIN local_package p ON s.local_package_id = p.id
      ORDER BY
          s.updated_at_ms DESC;
      `,
    )
    .all();
  return rows.map((row) => ({ ...row, enabled: row.enabled === 1 }));
}

export function dbSelectScheduleDetail(name: string): ScheduleDetails | undefined {
  loggerMain.debug("--dbSelectScheduleDetail--");
  const row = getDatabase()
    .prepare<[string], ScheduleDetailsRow>(
      `
      SELECT
          s.id,
          s.name,
          s.local_package_id,
          p.project_name,
          p.project_version,
          p.python_environment_name,
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
          INNER JOIN local_package p ON s.local_package_id = p.id
      WHERE
          s.name = ?;
      `,
    )
    .get(name);
  return row === undefined
    ? undefined
    : { ...row, ...convertRunSettingsRow(row), enabled: row.enabled === 1 };
}

export function dbSelectScheduleRunDetail(scheduleId: number): RunConfig | undefined {
  loggerMain.debug("--dbSelectScheduleRunDetail--");
  const row = getDatabase()
    .prepare<[number], ScheduleRunConfigRow>(
      `
      SELECT
          s.name AS schedule_name,
          s.run_conflict_policy,
          s.local_package_id,
          p.project_name,
          p.project_version,
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
          INNER JOIN local_package p ON s.local_package_id = p.id
      WHERE
          s.id = ?;
      `,
    )
    .get(scheduleId);
  return row === undefined ? undefined : { ...row, ...convertRunSettingsRow(row) };
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
              local_package_id,
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
      detailDict.local_package_id,
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
          local_package_id = ?,
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
      detailDict.local_package_id,
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
  const result = getDatabase()
    .prepare(
      `
      DELETE FROM
          schedule
      WHERE
          id = ?;
      `,
    )
    .run(id);
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
