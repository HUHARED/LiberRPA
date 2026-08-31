// FileName: rowValidation.ts

import type Database from "better-sqlite3";

import type { Dict_ProjectDetail } from "../../shared/project";
import type { Dict_RunHistory_Item } from "../../shared/run";
import type { Dict_ProjectRun_Detail } from "../Run/types";
import type { Dict_Detail_Schedule, Dict_ListItem_Schedule } from "../../shared/schedule";
import type { Arr_CustomProjectArgs } from "../../shared/runOptions";
import {
  ensureExactRecord,
  ensureString,
  ensureNonEmptyString,
  ensureNonNegativeInteger,
  ensurePositiveInteger,
  ensureRunTimeoutMinutes,
  ensureNullableString,
  ensureNullableNonNegativeInteger,
  ensureLogLevel,
  ensureRunConflictPolicy,
  ensureRunHistoryStatus,
  ensureCustomProjectArgs,
} from "../Common/validation";

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

export interface Dict_RunHistory_LogLocation {
  id: number;
  log_path: string;
}

function ensureBinaryInteger(value: unknown, sourceName: string): 0 | 1 {
  if (value !== 0 && value !== 1) {
    throw new Error(`${sourceName} must be 0 or 1.`);
  }
  return value;
}

function parseCustomProjectArgsJson(
  value: unknown,
  sourceName: string,
): Arr_CustomProjectArgs {
  const strValue = ensureString(value, sourceName);
  let parsedValue: unknown;
  try {
    parsedValue = JSON.parse(strValue);
  } catch (e: unknown) {
    throw new Error(`${sourceName} must contain valid JSON.`, { cause: e });
  }
  return ensureCustomProjectArgs(parsedValue, sourceName);
}

function ensureRows<T>(
  rows: unknown[],
  ensureRow: (value: unknown, sourceName: string) => T,
  sourceName: string,
): T[] {
  return rows.map((row, intIndex) => ensureRow(row, `${sourceName}[${intIndex}]`));
}

function ensureNameRow(value: unknown, sourceName: string): { name: string } {
  const row = ensureExactRecord(value, ["name"], sourceName);
  return { name: ensureNonEmptyString(row.name, `${sourceName}.name`) };
}

function ensureVersionRow(value: unknown, sourceName: string): { version: string } {
  const row = ensureExactRecord(value, ["version"], sourceName);
  return { version: ensureNonEmptyString(row.version, `${sourceName}.version`) };
}

export function ensureNameRows(rows: unknown[], sourceName: string): { name: string }[] {
  return ensureRows(rows, ensureNameRow, sourceName);
}

export function ensureVersionRows(
  rows: unknown[],
  sourceName: string,
): { version: string }[] {
  return ensureRows(rows, ensureVersionRow, sourceName);
}

export function ensureProjectDetailRow(
  value: unknown,
  sourceName: string,
): Dict_ProjectDetail {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "name",
      "version",
      "description",
      "version_summary",
      "python_environment_name",
      "timeout_min",
      "builtin_log_level",
      "builtin_record_video",
      "builtin_stop_shortcut",
      "builtin_highlight_ui",
      "custom_prj_args",
      "created_at_ms",
      "updated_at_ms",
    ],
    sourceName,
  );

  return {
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    name: ensureNonEmptyString(row.name, `${sourceName}.name`),
    version: ensureNonEmptyString(row.version, `${sourceName}.version`),
    description: ensureString(row.description, `${sourceName}.description`),
    version_summary: ensureString(row.version_summary, `${sourceName}.version_summary`),
    python_environment_name: ensureNonEmptyString(
      row.python_environment_name,
      `${sourceName}.python_environment_name`,
    ),
    timeout_min: ensureRunTimeoutMinutes(row.timeout_min, `${sourceName}.timeout_min`),
    builtin_log_level: ensureLogLevel(
      row.builtin_log_level,
      `${sourceName}.builtin_log_level`,
    ),
    builtin_record_video:
      ensureBinaryInteger(
        row.builtin_record_video,
        `${sourceName}.builtin_record_video`,
      ) === 1,
    builtin_stop_shortcut:
      ensureBinaryInteger(
        row.builtin_stop_shortcut,
        `${sourceName}.builtin_stop_shortcut`,
      ) === 1,
    builtin_highlight_ui:
      ensureBinaryInteger(
        row.builtin_highlight_ui,
        `${sourceName}.builtin_highlight_ui`,
      ) === 1,
    custom_prj_args: parseCustomProjectArgsJson(
      row.custom_prj_args,
      `${sourceName}.custom_prj_args`,
    ),
    created_at_ms: ensureNonNegativeInteger(
      row.created_at_ms,
      `${sourceName}.created_at_ms`,
    ),
    updated_at_ms: ensureNonNegativeInteger(
      row.updated_at_ms,
      `${sourceName}.updated_at_ms`,
    ),
  };
}

function ensureScheduleListItemRow(
  value: unknown,
  sourceName: string,
): Dict_ListItem_Schedule {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "name",
      "project_name",
      "project_version",
      "cron",
      "enable",
      "period_start_ms",
      "period_end_ms",
      "run_conflict_policy",
    ],
    sourceName,
  );
  const intPeriodStartMs = ensureNonNegativeInteger(
    row.period_start_ms,
    `${sourceName}.period_start_ms`,
  );
  const intPeriodEndMs = ensureNonNegativeInteger(
    row.period_end_ms,
    `${sourceName}.period_end_ms`,
  );
  if (intPeriodEndMs <= intPeriodStartMs) {
    throw new Error(`${sourceName}.period_end_ms must be greater than period_start_ms.`);
  }

  return {
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    name: ensureNonEmptyString(row.name, `${sourceName}.name`),
    project_name: ensureNonEmptyString(row.project_name, `${sourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${sourceName}.project_version`,
    ),
    cron: ensureNonEmptyString(row.cron, `${sourceName}.cron`),
    enable: ensureBinaryInteger(row.enable, `${sourceName}.enable`) === 1,
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    run_conflict_policy: ensureRunConflictPolicy(
      row.run_conflict_policy,
      `${sourceName}.run_conflict_policy`,
    ),
  };
}

export function ensureScheduleListRows(
  rows: unknown[],
  sourceName: string,
): Dict_ListItem_Schedule[] {
  return ensureRows(rows, ensureScheduleListItemRow, sourceName);
}

export function ensureScheduleDetailRow(
  value: unknown,
  sourceName: string,
): Dict_Detail_Schedule {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "name",
      "project_id",
      "project_name",
      "project_version",
      "cron",
      "run_conflict_policy",
      "period_start_ms",
      "period_end_ms",
      "enable",
      "timeout_min",
      "builtin_log_level",
      "builtin_record_video",
      "builtin_stop_shortcut",
      "builtin_highlight_ui",
      "custom_prj_args",
      "created_at_ms",
      "updated_at_ms",
    ],
    sourceName,
  );
  const intPeriodStartMs = ensureNonNegativeInteger(
    row.period_start_ms,
    `${sourceName}.period_start_ms`,
  );
  const intPeriodEndMs = ensureNonNegativeInteger(
    row.period_end_ms,
    `${sourceName}.period_end_ms`,
  );
  if (intPeriodEndMs <= intPeriodStartMs) {
    throw new Error(`${sourceName}.period_end_ms must be greater than period_start_ms.`);
  }

  return {
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    name: ensureNonEmptyString(row.name, `${sourceName}.name`),
    project_id: ensurePositiveInteger(row.project_id, `${sourceName}.project_id`),
    project_name: ensureNonEmptyString(row.project_name, `${sourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${sourceName}.project_version`,
    ),
    cron: ensureNonEmptyString(row.cron, `${sourceName}.cron`),
    run_conflict_policy: ensureRunConflictPolicy(
      row.run_conflict_policy,
      `${sourceName}.run_conflict_policy`,
    ),
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    enable: ensureBinaryInteger(row.enable, `${sourceName}.enable`) === 1,
    timeout_min: ensureRunTimeoutMinutes(row.timeout_min, `${sourceName}.timeout_min`),
    builtin_log_level: ensureLogLevel(
      row.builtin_log_level,
      `${sourceName}.builtin_log_level`,
    ),
    builtin_record_video:
      ensureBinaryInteger(
        row.builtin_record_video,
        `${sourceName}.builtin_record_video`,
      ) === 1,
    builtin_stop_shortcut:
      ensureBinaryInteger(
        row.builtin_stop_shortcut,
        `${sourceName}.builtin_stop_shortcut`,
      ) === 1,
    builtin_highlight_ui:
      ensureBinaryInteger(
        row.builtin_highlight_ui,
        `${sourceName}.builtin_highlight_ui`,
      ) === 1,
    custom_prj_args: parseCustomProjectArgsJson(
      row.custom_prj_args,
      `${sourceName}.custom_prj_args`,
    ),
    created_at_ms: ensureNonNegativeInteger(
      row.created_at_ms,
      `${sourceName}.created_at_ms`,
    ),
    updated_at_ms: ensureNonNegativeInteger(
      row.updated_at_ms,
      `${sourceName}.updated_at_ms`,
    ),
  };
}

export function ensureScheduleRunDetailRow(
  value: unknown,
  sourceName: string,
): Dict_ProjectRun_Detail {
  const row = ensureExactRecord(
    value,
    [
      "schedule_name",
      "id",
      "name",
      "version",
      "python_environment_name",
      "timeout_min",
      "builtin_log_level",
      "builtin_record_video",
      "builtin_stop_shortcut",
      "builtin_highlight_ui",
      "custom_prj_args",
    ],
    sourceName,
  );

  return {
    schedule_name: ensureNonEmptyString(row.schedule_name, `${sourceName}.schedule_name`),
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    name: ensureNonEmptyString(row.name, `${sourceName}.name`),
    version: ensureNonEmptyString(row.version, `${sourceName}.version`),
    python_environment_name: ensureNonEmptyString(
      row.python_environment_name,
      `${sourceName}.python_environment_name`,
    ),
    timeout_min: ensureRunTimeoutMinutes(row.timeout_min, `${sourceName}.timeout_min`),
    builtin_log_level: ensureLogLevel(
      row.builtin_log_level,
      `${sourceName}.builtin_log_level`,
    ),
    builtin_record_video:
      ensureBinaryInteger(
        row.builtin_record_video,
        `${sourceName}.builtin_record_video`,
      ) === 1,
    builtin_stop_shortcut:
      ensureBinaryInteger(
        row.builtin_stop_shortcut,
        `${sourceName}.builtin_stop_shortcut`,
      ) === 1,
    builtin_highlight_ui:
      ensureBinaryInteger(
        row.builtin_highlight_ui,
        `${sourceName}.builtin_highlight_ui`,
      ) === 1,
    custom_prj_args: parseCustomProjectArgsJson(
      row.custom_prj_args,
      `${sourceName}.custom_prj_args`,
    ),
  };
}

function ensureRunHistoryListItemRow(
  value: unknown,
  sourceName: string,
): Dict_RunHistory_Item {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "schedule_name",
      "project_name",
      "project_version",
      "python_environment_name",
      "run_started_at_ms",
      "run_ended_at_ms",
      "status",
    ],
    sourceName,
  );
  const status = ensureRunHistoryStatus(row.status, `${sourceName}.status`);
  const intRunEndedAtMs = ensureNullableNonNegativeInteger(
    row.run_ended_at_ms,
    `${sourceName}.run_ended_at_ms`,
  );
  if (
    ((status === "running" || status === "interrupted") && intRunEndedAtMs !== null) ||
    (status !== "running" && status !== "interrupted" && intRunEndedAtMs === null)
  ) {
    throw new Error(`${sourceName} has an inconsistent status and run_ended_at_ms.`);
  }

  return {
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    schedule_name: ensureNullableString(row.schedule_name, `${sourceName}.schedule_name`),
    project_name: ensureNonEmptyString(row.project_name, `${sourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${sourceName}.project_version`,
    ),
    python_environment_name: ensureNonEmptyString(
      row.python_environment_name,
      `${sourceName}.python_environment_name`,
    ),
    run_started_at_ms: ensureNonNegativeInteger(
      row.run_started_at_ms,
      `${sourceName}.run_started_at_ms`,
    ),
    run_ended_at_ms: intRunEndedAtMs,
    status,
  };
}

export function ensureRunHistoryListRows(
  rows: unknown[],
  sourceName: string,
): Dict_RunHistory_Item[] {
  return ensureRows(rows, ensureRunHistoryListItemRow, sourceName);
}

export function ensureCountRow(
  value: unknown,
  strColumnName: string,
  sourceName: string,
): number {
  const row = ensureExactRecord(value, [strColumnName], sourceName);
  return ensureNonNegativeInteger(row[strColumnName], `${sourceName}.${strColumnName}`);
}

export function ensureRunHistoryLogLocationRow(
  value: unknown,
  sourceName: string,
): Dict_RunHistory_LogLocation {
  const row = ensureExactRecord(value, ["id", "log_path"], sourceName);
  return {
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    log_path: ensureNonEmptyString(row.log_path, `${sourceName}.log_path`),
  };
}
