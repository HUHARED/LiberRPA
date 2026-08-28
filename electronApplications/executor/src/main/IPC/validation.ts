// FileName: validation.ts

import type { Dict_ProjectSettingsUpdate } from "../../shared/project";
import type { Dict_RunHistory_Options } from "../../shared/run";
import type { Dict_ScheduleCreate, Dict_ScheduleUpdate } from "../../shared/schedule";
import type { Str_ExecutorInvokeCommand, Str_RendererLogLevel } from "../../shared/ipc";
import {
  ensureExactRecord,
  ensureString,
  ensureNonEmptyString,
  ensureTrimmedSingleLineString,
  ensureBoolean,
  ensureNonNegativeInteger,
  ensurePositiveInteger,
  ensureRunTimeoutMinutes,
  ensureLogLevel,
  ensureRunConflictPolicy,
  ensureRunHistoryStatus,
  ensureCustomProjectArgs,
} from "../Common/validation";

function ensureRunHistorySortKey(
  value: unknown,
  strSourceName: string,
): Dict_RunHistory_Options["sortBy"][number]["key"] {
  switch (value) {
    case "schedule_name":
    case "project_name":
    case "project_version":
    case "python_environment_name":
    case "run_started_at_ms":
    case "run_ended_at_ms":
    case "status":
      return value;
    default:
      throw new Error(`${strSourceName} contains an unsupported sort key.`);
  }
}

function ensureRunHistorySortOrder(value: unknown, strSourceName: string): "asc" | "desc" {
  if (value === "asc" || value === "desc") {
    return value;
  }
  throw new Error(`${strSourceName} must be 'asc' or 'desc'.`);
}

export function ensureInvokeCommand(value: unknown): Str_ExecutorInvokeCommand {
  switch (value) {
    case "openProjectLogFolder":
    case "saveExecutorConfig":
    case "runProject":
    case "getPythonEnvironmentNames":
    case "installProjectPackage":
    case "getProjectNames":
    case "getProjectVersions":
    case "getProjectDetail":
    case "saveProjectSettings":
    case "getProjectBoundSchedules":
    case "deleteProject":
    case "getScheduleList":
    case "getScheduleDetail":
    case "createSchedule":
    case "saveSchedule":
    case "deleteSchedule":
    case "getRunHistoryPage":
    case "getRunQueue":
    case "cancelWaitingRun":
    case "openRunLogFolder":
    case "runMostRecentlyInstalledProjectVersion":
    case "pythonCancel":
    case "chooseProjectLogFolder":
      return value;
    default:
      throw new Error(`Unknown Renderer invoke command: ${String(value)}`);
  }
}

export function ensureRendererLogLevel(value: unknown): Str_RendererLogLevel {
  switch (value) {
    case "error":
    case "warn":
    case "info":
    case "http":
    case "verbose":
    case "debug":
    case "silly":
      return value;
    default:
      throw new Error(`Unknown Renderer log level: ${String(value)}`);
  }
}

export function ensureNoData(value: unknown, command: string): undefined {
  if (value !== undefined) {
    throw new Error(`${command} does not accept request data.`);
  }
  return undefined;
}

export function ensureStringData(value: unknown, command: string): string {
  return ensureString(value, `${command} data`);
}

export function ensurePositiveIntegerData(value: unknown, command: string): number {
  return ensurePositiveInteger(value, `${command} data`);
}

export function ensureProjectRef(value: unknown): { name: string; version: string } {
  const dictValue = ensureExactRecord(value, ["name", "version"], "Project reference");
  return {
    name: ensureNonEmptyString(dictValue.name, "Project reference.name"),
    version: ensureNonEmptyString(dictValue.version, "Project reference.version"),
  };
}

export function ensureWaitingRunId(value: unknown): string {
  return ensureNonEmptyString(value, "Waiting Run ID");
}

export function ensureProjectSettingsUpdate(value: unknown): Dict_ProjectSettingsUpdate {
  const dictValue = ensureExactRecord(
    value,
    [
      "id",
      "python_environment_name",
      "timeout_min",
      "builtin_log_level",
      "builtin_record_video",
      "builtin_stop_shortcut",
      "builtin_highlight_ui",
      "custom_prj_args",
    ],
    "Project settings update request",
  );

  return {
    id: ensurePositiveInteger(dictValue.id, "Project settings update request.id"),
    python_environment_name: ensureNonEmptyString(
      dictValue.python_environment_name,
      "Project settings update request.python_environment_name",
    ),
    timeout_min: ensureRunTimeoutMinutes(
      dictValue.timeout_min,
      "Project settings update request.timeout_min",
    ),
    builtin_log_level: ensureLogLevel(
      dictValue.builtin_log_level,
      "Project settings update request.builtin_log_level",
    ),
    builtin_record_video: ensureBoolean(
      dictValue.builtin_record_video,
      "Project settings update request.builtin_record_video",
    ),
    builtin_stop_shortcut: ensureBoolean(
      dictValue.builtin_stop_shortcut,
      "Project settings update request.builtin_stop_shortcut",
    ),
    builtin_highlight_ui: ensureBoolean(
      dictValue.builtin_highlight_ui,
      "Project settings update request.builtin_highlight_ui",
    ),
    custom_prj_args: ensureCustomProjectArgs(
      dictValue.custom_prj_args,
      "Project settings update request.custom_prj_args",
    ),
  };
}

function ensureScheduleData(
  value: unknown,
  boolIncludeId: boolean,
): Dict_ScheduleCreate | Dict_ScheduleUpdate {
  const arrExpectedKey = [
    "name",
    "project_id",
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
  ];
  if (boolIncludeId) {
    arrExpectedKey.unshift("id");
  }

  const dictValue = ensureExactRecord(value, arrExpectedKey, "Schedule request");
  const intPeriodStartMs = ensureNonNegativeInteger(
    dictValue.period_start_ms,
    "Schedule request.period_start_ms",
  );
  const intPeriodEndMs = ensureNonNegativeInteger(
    dictValue.period_end_ms,
    "Schedule request.period_end_ms",
  );
  if (intPeriodEndMs <= intPeriodStartMs) {
    throw new Error("Schedule request.period_end_ms must be greater than period_start_ms.");
  }

  const dictBase: Dict_ScheduleCreate = {
    name: ensureTrimmedSingleLineString(dictValue.name, "Schedule request.name"),
    project_id: ensurePositiveInteger(dictValue.project_id, "Schedule request.project_id"),
    cron: ensureNonEmptyString(dictValue.cron, "Schedule request.cron"),
    run_conflict_policy: ensureRunConflictPolicy(
      dictValue.run_conflict_policy,
      "Schedule request.run_conflict_policy",
    ),
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    enable: ensureBoolean(dictValue.enable, "Schedule request.enable"),
    timeout_min: ensureRunTimeoutMinutes(
      dictValue.timeout_min,
      "Schedule request.timeout_min",
    ),
    builtin_log_level: ensureLogLevel(
      dictValue.builtin_log_level,
      "Schedule request.builtin_log_level",
    ),
    builtin_record_video: ensureBoolean(
      dictValue.builtin_record_video,
      "Schedule request.builtin_record_video",
    ),
    builtin_stop_shortcut: ensureBoolean(
      dictValue.builtin_stop_shortcut,
      "Schedule request.builtin_stop_shortcut",
    ),
    builtin_highlight_ui: ensureBoolean(
      dictValue.builtin_highlight_ui,
      "Schedule request.builtin_highlight_ui",
    ),
    custom_prj_args: ensureCustomProjectArgs(
      dictValue.custom_prj_args,
      "Schedule request.custom_prj_args",
    ),
  };

  if (!boolIncludeId) {
    return dictBase;
  }

  return {
    id: ensurePositiveInteger(dictValue.id, "Schedule request.id"),
    ...dictBase,
  };
}

export function ensureScheduleCreate(value: unknown): Dict_ScheduleCreate {
  return ensureScheduleData(value, false);
}

export function ensureScheduleUpdate(value: unknown): Dict_ScheduleUpdate {
  const dictValue = ensureScheduleData(value, true);
  if (!("id" in dictValue)) {
    throw new Error("Schedule update request is missing id.");
  }
  return dictValue;
}

export function ensureRunHistoryOptions(value: unknown): Dict_RunHistory_Options {
  const dictValue = ensureExactRecord(
    value,
    ["page", "itemsPerPage", "sortBy", "search"],
    "Run History options",
  );

  if (!Array.isArray(dictValue.sortBy)) {
    throw new Error("Run History options.sortBy must be an array.");
  }
  const arrSortBy = dictValue.sortBy.map((item, intIndex) => {
    const dictSort = ensureExactRecord(
      item,
      ["key", "order"],
      `Run History options.sortBy[${intIndex}]`,
    );
    const strKey = ensureRunHistorySortKey(
      dictSort.key,
      `Run History options.sortBy[${intIndex}].key`,
    );
    const strOrder = ensureRunHistorySortOrder(
      dictSort.order,
      `Run History options.sortBy[${intIndex}].order`,
    );
    return { key: strKey, order: strOrder };
  });

  const dictSearch = ensureExactRecord(
    dictValue.search,
    ["schedule_name", "project_name", "project_version", "status"],
    "Run History options.search",
  );

  const status =
    dictSearch.status === null
      ? null
      : ensureRunHistoryStatus(dictSearch.status, "Run History options.search.status");

  return {
    page: ensurePositiveInteger(dictValue.page, "Run History options.page"),
    itemsPerPage: ensurePositiveInteger(
      dictValue.itemsPerPage,
      "Run History options.itemsPerPage",
    ),
    sortBy: arrSortBy,
    search: {
      schedule_name: ensureString(
        dictSearch.schedule_name,
        "Run History options.search.schedule_name",
      ),
      project_name: ensureString(
        dictSearch.project_name,
        "Run History options.search.project_name",
      ),
      project_version: ensureString(
        dictSearch.project_version,
        "Run History options.search.project_version",
      ),
      status,
    },
  };
}
