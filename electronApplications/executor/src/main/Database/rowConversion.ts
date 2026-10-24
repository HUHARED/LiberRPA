// FileName: rowConversion.ts

import type Database from "better-sqlite3";

import type { CustomProjectArgs, RunSettings } from "../../shared/runSettings";

export interface RunSettingsRow extends Omit<
  RunSettings,
  | "builtin_record_video"
  | "builtin_stop_shortcut"
  | "builtin_highlight_ui"
  | "custom_prj_args"
> {
  builtin_record_video: 0 | 1;
  builtin_stop_shortcut: 0 | 1;
  builtin_highlight_ui: 0 | 1;
  custom_prj_args: string;
}

export function convertRunSettingsRow(row: RunSettingsRow): RunSettings {
  return {
    max_retry_count: row.max_retry_count,
    timeout_min: row.timeout_min,
    builtin_log_level: row.builtin_log_level,
    builtin_record_video: row.builtin_record_video === 1,
    builtin_stop_shortcut: row.builtin_stop_shortcut === 1,
    builtin_highlight_ui: row.builtin_highlight_ui === 1,
    custom_prj_args: JSON.parse(row.custom_prj_args) as CustomProjectArgs,
  };
}

export function ensureSingleRowAffected(
  result: Database.RunResult,
  operationName: string,
): void {
  if (result.changes !== 1) {
    throw new Error(
      `${operationName} must affect exactly one database row, but affected ${String(result.changes)}.`,
    );
  }
}
