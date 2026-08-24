import type { DictColumns_Project_Detail_DB } from "../../shared/project";
import type { DictColumns_RunHistory_ListItem_DB } from "../../shared/run";
import type {
  DictColumns_Schedule_Detail_DB,
  DictColumns_Schedule_ListItem_DB,
} from "../../shared/schedule";
import {
  ensureBinaryInteger,
  ensureCustomProjectArgsJson,
  ensureExactRecord,
  ensureRunHistoryStatus,
  ensureLogLevel,
  ensureNonEmptyString,
  ensureNonNegativeInteger,
  ensureNullableNonNegativeInteger,
  ensureNullableString,
  ensurePositiveInteger,
  ensureProjectSource,
  ensureString,
  ensureWhenOthersRunning,
} from "../Common/validation";

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
): DictColumns_Project_Detail_DB {
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
    builtin_record_video: ensureBinaryInteger(
      row.builtin_record_video,
      `${strSourceName}.builtin_record_video`,
    ),
    builtin_stop_shortcut: ensureBinaryInteger(
      row.builtin_stop_shortcut,
      `${strSourceName}.builtin_stop_shortcut`,
    ),
    builtin_highlight_ui: ensureBinaryInteger(
      row.builtin_highlight_ui,
      `${strSourceName}.builtin_highlight_ui`,
    ),
    custom_prj_args: ensureCustomProjectArgsJson(
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
): DictColumns_Schedule_ListItem_DB {
  const row = ensureExactRecord(
    value,
    [
      "name",
      "project_source",
      "project_name",
      "project_version",
      "cron",
      "enable",
      "period_start_ms",
      "period_end_ms",
      "when_others_running",
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
    project_source: ensureProjectSource(
      row.project_source,
      `${strSourceName}.project_source`,
    ),
    project_name: ensureNonEmptyString(row.project_name, `${strSourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${strSourceName}.project_version`,
    ),
    cron: ensureNonEmptyString(row.cron, `${strSourceName}.cron`),
    enable: ensureBinaryInteger(row.enable, `${strSourceName}.enable`),
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    when_others_running: ensureWhenOthersRunning(
      row.when_others_running,
      `${strSourceName}.when_others_running`,
    ),
  };
}

export function ensureScheduleListRows(
  rows: unknown[],
  strSourceName: string,
): DictColumns_Schedule_ListItem_DB[] {
  return ensureRows(rows, ensureScheduleListItemRow, strSourceName);
}

export function ensureScheduleDetailRow(
  value: unknown,
  strSourceName: string,
): DictColumns_Schedule_Detail_DB {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "name",
      "project_source",
      "project_id",
      "project_name",
      "project_version",
      "python_environment_name",
      "cron",
      "when_others_running",
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
    project_source: ensureProjectSource(
      row.project_source,
      `${strSourceName}.project_source`,
    ),
    project_id: ensurePositiveInteger(row.project_id, `${strSourceName}.project_id`),
    project_name: ensureNonEmptyString(row.project_name, `${strSourceName}.project_name`),
    project_version: ensureNonEmptyString(
      row.project_version,
      `${strSourceName}.project_version`,
    ),
    python_environment_name: ensureNonEmptyString(
      row.python_environment_name,
      `${strSourceName}.python_environment_name`,
    ),
    cron: ensureNonEmptyString(row.cron, `${strSourceName}.cron`),
    when_others_running: ensureWhenOthersRunning(
      row.when_others_running,
      `${strSourceName}.when_others_running`,
    ),
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    enable: ensureBinaryInteger(row.enable, `${strSourceName}.enable`),
    timeout_min: ensureNonNegativeInteger(row.timeout_min, `${strSourceName}.timeout_min`),
    builtin_log_level: ensureLogLevel(
      row.builtin_log_level,
      `${strSourceName}.builtin_log_level`,
    ),
    builtin_record_video: ensureBinaryInteger(
      row.builtin_record_video,
      `${strSourceName}.builtin_record_video`,
    ),
    builtin_stop_shortcut: ensureBinaryInteger(
      row.builtin_stop_shortcut,
      `${strSourceName}.builtin_stop_shortcut`,
    ),
    builtin_highlight_ui: ensureBinaryInteger(
      row.builtin_highlight_ui,
      `${strSourceName}.builtin_highlight_ui`,
    ),
    custom_prj_args: ensureCustomProjectArgsJson(
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

function ensureRunHistoryListItemRow(
  value: unknown,
  strSourceName: string,
): DictColumns_RunHistory_ListItem_DB {
  const row = ensureExactRecord(
    value,
    [
      "id",
      "scheduler_name",
      "project_source",
      "project_name",
      "project_version",
      "python_environment_name",
      "run_started_at_ms",
      "run_ended_at_ms",
      "status",
      "log_path",
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
    scheduler_name: ensureNullableString(
      row.scheduler_name,
      `${strSourceName}.scheduler_name`,
    ),
    project_source: ensureProjectSource(
      row.project_source,
      `${strSourceName}.project_source`,
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
    log_path: ensureNonEmptyString(row.log_path, `${strSourceName}.log_path`),
  };
}

export function ensureRunHistoryListRows(
  rows: unknown[],
  strSourceName: string,
): DictColumns_RunHistory_ListItem_DB[] {
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

function ensureLogPathRow(value: unknown, strSourceName: string): { log_path: string } {
  const row = ensureExactRecord(value, ["log_path"], strSourceName);
  return { log_path: ensureNonEmptyString(row.log_path, `${strSourceName}.log_path`) };
}

export function ensureLogPathRows(rows: unknown[], strSourceName: string): string[] {
  return ensureRows(rows, ensureLogPathRow, strSourceName).map((row) => row.log_path);
}
