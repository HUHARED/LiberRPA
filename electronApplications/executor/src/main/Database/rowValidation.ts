// FileName: rowValidation.ts

import type Database from "better-sqlite3";

import type { ProjectDetails } from "../../shared/project";
import { type ProjectRunConfig, RunStatus, type RunHistoryItem } from "../../shared/run";

import type { ScheduleDetails, ScheduleListItem } from "../../shared/schedule";
import type { CustomProjectArgs } from "../../shared/runSettings";
import {
  ensureExactRecord,
  ensureString,
  ensureNonEmptyString,
  ensurePackageDescription,
  ensureVersionSummary,
  ensurePythonEnvironmentName,
  ensureNonNegativeInteger,
  ensurePositiveInteger,
  ensureMaxRetryCount,
  ensureRunTimeoutMinutes,
  ensureNullableString,
  ensureNullableNonNegativeInteger,
  ensureLogLevel,
  ensureRunConflictPolicy,
  ensureRunSource,
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

export interface RunLogLocation {
  id: number;
  run_id: string;
  log_path: string;
  record_video: boolean;
  finished_at_ms: number;
}

function ensureBinaryInteger(value: unknown, sourceName: string): 0 | 1 {
  if (value !== 0 && value !== 1) {
    throw new Error(`${sourceName} must be 0 or 1.`);
  }
  return value;
}

function parseCustomProjectArgsJson(value: unknown, sourceName: string): CustomProjectArgs {
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

export function ensureProjectDetailRow(value: unknown, sourceName: string): ProjectDetails {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "name",
      "version",
      "description",
      "version_summary",
      "python_environment_name",
      "max_retry_count",
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
    description: ensurePackageDescription(row.description, `${sourceName}.description`),
    version_summary: ensureVersionSummary(
      row.version_summary,
      `${sourceName}.version_summary`,
    ),
    python_environment_name: ensurePythonEnvironmentName(
      row.python_environment_name,
      `${sourceName}.python_environment_name`,
    ),
    max_retry_count: ensureMaxRetryCount(
      row.max_retry_count,
      `${sourceName}.max_retry_count`,
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

function ensureScheduleListItemRow(value: unknown, sourceName: string): ScheduleListItem {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "name",
      "project_name",
      "project_version",
      "cron",
      "enabled",
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
    enabled: ensureBinaryInteger(row.enabled, `${sourceName}.enabled`) === 1,
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
): ScheduleListItem[] {
  return ensureRows(rows, ensureScheduleListItemRow, sourceName);
}

export function ensureScheduleDetailRow(
  value: unknown,
  sourceName: string,
): ScheduleDetails {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "name",
      "project_id",
      "project_name",
      "project_version",
      "python_environment_name",
      "cron",
      "run_conflict_policy",
      "period_start_ms",
      "period_end_ms",
      "enabled",
      "max_retry_count",
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
    python_environment_name: ensurePythonEnvironmentName(
      row.python_environment_name,
      `${sourceName}.python_environment_name`,
    ),
    cron: ensureNonEmptyString(row.cron, `${sourceName}.cron`),
    run_conflict_policy: ensureRunConflictPolicy(
      row.run_conflict_policy,
      `${sourceName}.run_conflict_policy`,
    ),
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    enabled: ensureBinaryInteger(row.enabled, `${sourceName}.enabled`) === 1,
    max_retry_count: ensureMaxRetryCount(
      row.max_retry_count,
      `${sourceName}.max_retry_count`,
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

export function ensureScheduleRunDetailRow(
  value: unknown,
  sourceName: string,
): ProjectRunConfig {
  const row = ensureExactRecord(
    value,
    [
      "schedule_name",
      "run_conflict_policy",
      "local_project_id",
      "project_name",
      "project_version",
      "python_environment_name",
      "max_retry_count",
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
    run_conflict_policy: ensureRunConflictPolicy(
      row.run_conflict_policy,
      `${sourceName}.run_conflict_policy`,
    ),
    local_project_id: ensurePositiveInteger(
      row.local_project_id,
      `${sourceName}.local_project_id`,
    ),
    project_name: ensureNonEmptyString(row.project_name, `${sourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${sourceName}.project_version`,
    ),
    python_environment_name: ensurePythonEnvironmentName(
      row.python_environment_name,
      `${sourceName}.python_environment_name`,
    ),
    max_retry_count: ensureMaxRetryCount(
      row.max_retry_count,
      `${sourceName}.max_retry_count`,
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

function ensureRunHistoryListItemRow(value: unknown, sourceName: string): RunHistoryItem {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "source",
      "attempt_number",
      "schedule_name",
      "project_name",
      "project_version",
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
  const boolEndTimeUnknown = status === RunStatus.Running || status === RunStatus.Unknown;
  if (
    (boolEndTimeUnknown && intRunEndedAtMs !== null) ||
    (!boolEndTimeUnknown && status !== RunStatus.Interrupted && intRunEndedAtMs === null)
  ) {
    throw new Error(`${sourceName} has an inconsistent status and run_ended_at_ms.`);
  }

  return {
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    source: ensureRunSource(row.source, `${sourceName}.source`),
    attempt_number: ensurePositiveInteger(
      row.attempt_number,
      `${sourceName}.attempt_number`,
    ),
    schedule_name: ensureNullableString(row.schedule_name, `${sourceName}.schedule_name`),
    project_name: ensureNonEmptyString(row.project_name, `${sourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${sourceName}.project_version`,
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
): RunHistoryItem[] {
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
): RunLogLocation {
  const row = ensureExactRecord(
    value,
    ["id", "run_id", "log_path", "record_video", "finished_at_ms"],
    sourceName,
  );
  return {
    id: ensurePositiveInteger(row.id, `${sourceName}.id`),
    run_id: ensureNonEmptyString(row.run_id, `${sourceName}.run_id`),
    log_path: ensureNonEmptyString(row.log_path, `${sourceName}.log_path`),
    record_video: ensureBinaryInteger(row.record_video, `${sourceName}.record_video`) === 1,
    finished_at_ms: ensureNonNegativeInteger(
      row.finished_at_ms,
      `${sourceName}.finished_at_ms`,
    ),
  };
}
