import type { DictProjectDetail } from "../../shared/project";
import type { DictRunHistoryItem } from "../../shared/run";
import type { DictProjectRunDetail } from "../Run/types";
import type { DictScheduleDetail, DictScheduleListItem } from "../../shared/schedule";
import type { TypeCustomProjectArgs } from "../../shared/runOptions";
import {
  ensureCustomProjectArgs,
  ensureExactRecord,
  ensureLogLevel,
  ensureNonEmptyString,
  ensureNonNegativeInteger,
  ensureNullableNonNegativeInteger,
  ensureNullableString,
  ensurePositiveInteger,
  ensureRunHistoryStatus,
  ensureString,
  ensureRunConflictPolicy,
} from "../Common/validation";

function ensureBinaryInteger(value: unknown, strSourceName: string): 0 | 1 {
  if (value !== 0 && value !== 1) {
    throw new Error(`${strSourceName} must be 0 or 1.`);
  }
  return value;
}

function parseCustomProjectArgsJson(
  value: unknown,
  strSourceName: string,
): TypeCustomProjectArgs {
  const strValue = ensureString(value, strSourceName);
  let parsedValue: unknown;
  try {
    parsedValue = JSON.parse(strValue);
  } catch (e: unknown) {
    throw new Error(`${strSourceName} must contain valid JSON.`, { cause: e });
  }
  return ensureCustomProjectArgs(parsedValue, strSourceName);
}

function ensureRows<T>(
  rows: unknown[],
  ensureRow: (value: unknown, strSourceName: string) => T,
  strSourceName: string,
): T[] {
  return rows.map((row, intIndex) => ensureRow(row, `${strSourceName}[${intIndex}]`));
}

function ensureNameRow(value: unknown, strSourceName: string): { name: string } {
  const row = ensureExactRecord(value, ["name"], strSourceName);
  return { name: ensureNonEmptyString(row.name, `${strSourceName}.name`) };
}

function ensureVersionRow(value: unknown, strSourceName: string): { version: string } {
  const row = ensureExactRecord(value, ["version"], strSourceName);
  return { version: ensureNonEmptyString(row.version, `${strSourceName}.version`) };
}

export function ensureNameRows(rows: unknown[], strSourceName: string): { name: string }[] {
  return ensureRows(rows, ensureNameRow, strSourceName);
}

export function ensureVersionRows(
  rows: unknown[],
  strSourceName: string,
): { version: string }[] {
  return ensureRows(rows, ensureVersionRow, strSourceName);
}

export function ensureProjectDetailRow(
  value: unknown,
  strSourceName: string,
): DictProjectDetail {
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
    strSourceName,
  );

  return {
    id: ensurePositiveInteger(row.id, `${strSourceName}.id`),
    name: ensureNonEmptyString(row.name, `${strSourceName}.name`),
    version: ensureNonEmptyString(row.version, `${strSourceName}.version`),
    description: ensureString(row.description, `${strSourceName}.description`),
    version_summary: ensureString(row.version_summary, `${strSourceName}.version_summary`),
    python_environment_name: ensureNonEmptyString(
      row.python_environment_name,
      `${strSourceName}.python_environment_name`,
    ),
    timeout_min: ensureNonNegativeInteger(row.timeout_min, `${strSourceName}.timeout_min`),
    builtin_log_level: ensureLogLevel(
      row.builtin_log_level,
      `${strSourceName}.builtin_log_level`,
    ),
    builtin_record_video:
      ensureBinaryInteger(
        row.builtin_record_video,
        `${strSourceName}.builtin_record_video`,
      ) === 1,
    builtin_stop_shortcut:
      ensureBinaryInteger(
        row.builtin_stop_shortcut,
        `${strSourceName}.builtin_stop_shortcut`,
      ) === 1,
    builtin_highlight_ui:
      ensureBinaryInteger(
        row.builtin_highlight_ui,
        `${strSourceName}.builtin_highlight_ui`,
      ) === 1,
    custom_prj_args: parseCustomProjectArgsJson(
      row.custom_prj_args,
      `${strSourceName}.custom_prj_args`,
    ),
    created_at_ms: ensureNonNegativeInteger(
      row.created_at_ms,
      `${strSourceName}.created_at_ms`,
    ),
    updated_at_ms: ensureNonNegativeInteger(
      row.updated_at_ms,
      `${strSourceName}.updated_at_ms`,
    ),
  };
}

function ensureScheduleListItemRow(
  value: unknown,
  strSourceName: string,
): DictScheduleListItem {
  const row = ensureExactRecord(
    value,
    [
      "name",
      "project_name",
      "project_version",
      "cron",
      "enable",
      "period_start_ms",
      "period_end_ms",
      "run_conflict_policy",
    ],
    strSourceName,
  );
  const intPeriodStartMs = ensureNonNegativeInteger(
    row.period_start_ms,
    `${strSourceName}.period_start_ms`,
  );
  const intPeriodEndMs = ensureNonNegativeInteger(
    row.period_end_ms,
    `${strSourceName}.period_end_ms`,
  );
  if (intPeriodEndMs <= intPeriodStartMs) {
    throw new Error(`${strSourceName}.period_end_ms must be greater than period_start_ms.`);
  }

  return {
    name: ensureNonEmptyString(row.name, `${strSourceName}.name`),
    project_name: ensureNonEmptyString(row.project_name, `${strSourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${strSourceName}.project_version`,
    ),
    cron: ensureNonEmptyString(row.cron, `${strSourceName}.cron`),
    enable: ensureBinaryInteger(row.enable, `${strSourceName}.enable`) === 1,
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    run_conflict_policy: ensureRunConflictPolicy(
      row.run_conflict_policy,
      `${strSourceName}.run_conflict_policy`,
    ),
  };
}

export function ensureScheduleListRows(
  rows: unknown[],
  strSourceName: string,
): DictScheduleListItem[] {
  return ensureRows(rows, ensureScheduleListItemRow, strSourceName);
}

export function ensureScheduleDetailRow(
  value: unknown,
  strSourceName: string,
): DictScheduleDetail {
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
    strSourceName,
  );
  const intPeriodStartMs = ensureNonNegativeInteger(
    row.period_start_ms,
    `${strSourceName}.period_start_ms`,
  );
  const intPeriodEndMs = ensureNonNegativeInteger(
    row.period_end_ms,
    `${strSourceName}.period_end_ms`,
  );
  if (intPeriodEndMs <= intPeriodStartMs) {
    throw new Error(`${strSourceName}.period_end_ms must be greater than period_start_ms.`);
  }

  return {
    id: ensurePositiveInteger(row.id, `${strSourceName}.id`),
    name: ensureNonEmptyString(row.name, `${strSourceName}.name`),
    project_id: ensurePositiveInteger(row.project_id, `${strSourceName}.project_id`),
    project_name: ensureNonEmptyString(row.project_name, `${strSourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${strSourceName}.project_version`,
    ),
    cron: ensureNonEmptyString(row.cron, `${strSourceName}.cron`),
    run_conflict_policy: ensureRunConflictPolicy(
      row.run_conflict_policy,
      `${strSourceName}.run_conflict_policy`,
    ),
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    enable: ensureBinaryInteger(row.enable, `${strSourceName}.enable`) === 1,
    timeout_min: ensureNonNegativeInteger(row.timeout_min, `${strSourceName}.timeout_min`),
    builtin_log_level: ensureLogLevel(
      row.builtin_log_level,
      `${strSourceName}.builtin_log_level`,
    ),
    builtin_record_video:
      ensureBinaryInteger(
        row.builtin_record_video,
        `${strSourceName}.builtin_record_video`,
      ) === 1,
    builtin_stop_shortcut:
      ensureBinaryInteger(
        row.builtin_stop_shortcut,
        `${strSourceName}.builtin_stop_shortcut`,
      ) === 1,
    builtin_highlight_ui:
      ensureBinaryInteger(
        row.builtin_highlight_ui,
        `${strSourceName}.builtin_highlight_ui`,
      ) === 1,
    custom_prj_args: parseCustomProjectArgsJson(
      row.custom_prj_args,
      `${strSourceName}.custom_prj_args`,
    ),
    created_at_ms: ensureNonNegativeInteger(
      row.created_at_ms,
      `${strSourceName}.created_at_ms`,
    ),
    updated_at_ms: ensureNonNegativeInteger(
      row.updated_at_ms,
      `${strSourceName}.updated_at_ms`,
    ),
  };
}

export function ensureScheduleRunDetailRow(
  value: unknown,
  strSourceName: string,
): DictProjectRunDetail {
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
    strSourceName,
  );

  return {
    schedule_name: ensureNonEmptyString(
      row.schedule_name,
      `${strSourceName}.schedule_name`,
    ),
    id: ensurePositiveInteger(row.id, `${strSourceName}.id`),
    name: ensureNonEmptyString(row.name, `${strSourceName}.name`),
    version: ensureNonEmptyString(row.version, `${strSourceName}.version`),
    python_environment_name: ensureNonEmptyString(
      row.python_environment_name,
      `${strSourceName}.python_environment_name`,
    ),
    timeout_min: ensureNonNegativeInteger(row.timeout_min, `${strSourceName}.timeout_min`),
    builtin_log_level: ensureLogLevel(
      row.builtin_log_level,
      `${strSourceName}.builtin_log_level`,
    ),
    builtin_record_video:
      ensureBinaryInteger(
        row.builtin_record_video,
        `${strSourceName}.builtin_record_video`,
      ) === 1,
    builtin_stop_shortcut:
      ensureBinaryInteger(
        row.builtin_stop_shortcut,
        `${strSourceName}.builtin_stop_shortcut`,
      ) === 1,
    builtin_highlight_ui:
      ensureBinaryInteger(
        row.builtin_highlight_ui,
        `${strSourceName}.builtin_highlight_ui`,
      ) === 1,
    custom_prj_args: parseCustomProjectArgsJson(
      row.custom_prj_args,
      `${strSourceName}.custom_prj_args`,
    ),
  };
}

function ensureRunHistoryListItemRow(
  value: unknown,
  strSourceName: string,
): DictRunHistoryItem {
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
    strSourceName,
  );
  const status = ensureRunHistoryStatus(row.status, `${strSourceName}.status`);
  const intRunEndedAtMs = ensureNullableNonNegativeInteger(
    row.run_ended_at_ms,
    `${strSourceName}.run_ended_at_ms`,
  );
  if (
    ((status === "running" || status === "interrupted") && intRunEndedAtMs !== null) ||
    (status !== "running" && status !== "interrupted" && intRunEndedAtMs === null)
  ) {
    throw new Error(`${strSourceName} has an inconsistent status and run_ended_at_ms.`);
  }

  return {
    id: ensurePositiveInteger(row.id, `${strSourceName}.id`),
    schedule_name: ensureNullableString(
      row.schedule_name,
      `${strSourceName}.schedule_name`,
    ),
    project_name: ensureNonEmptyString(row.project_name, `${strSourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${strSourceName}.project_version`,
    ),
    python_environment_name: ensureNonEmptyString(
      row.python_environment_name,
      `${strSourceName}.python_environment_name`,
    ),
    run_started_at_ms: ensureNonNegativeInteger(
      row.run_started_at_ms,
      `${strSourceName}.run_started_at_ms`,
    ),
    run_ended_at_ms: intRunEndedAtMs,
    status,
  };
}

export function ensureRunHistoryListRows(
  rows: unknown[],
  strSourceName: string,
): DictRunHistoryItem[] {
  return ensureRows(rows, ensureRunHistoryListItemRow, strSourceName);
}

export function ensureCountRow(
  value: unknown,
  strColumnName: string,
  strSourceName: string,
): number {
  const row = ensureExactRecord(value, [strColumnName], strSourceName);
  return ensureNonNegativeInteger(row[strColumnName], `${strSourceName}.${strColumnName}`);
}

export function ensureLogPathRow(value: unknown, strSourceName: string): string {
  const row = ensureExactRecord(value, ["log_path"], strSourceName);
  return ensureNonEmptyString(row.log_path, `${strSourceName}.log_path`);
}

export function ensureLogPathRows(rows: unknown[], strSourceName: string): string[] {
  return ensureRows(rows, ensureLogPathRow, strSourceName);
}
