// FileName: ipcValidation.ts

import type {
  DictColumns_Project_Detail_Run,
  DictColumns_Project_Detail_ToUpdate,
  DictColumns_Scheduler_Detail_ToInsert,
  DictColumns_Scheduler_Detail_ToUpdate,
  Dict_History_Options,
} from "../shared/interface";
import type { TypeExecutorInvokeCommand, TypeRendererLogLevel } from "../shared/ipc";

import {
  ensureBinaryInteger,
  ensureBoolean,
  ensureCustomProjectArgs,
  ensureCustomProjectArgsJson,
  ensureExactRecord,
  ensureFiniteNumber,
  ensureHistoryStatus,
  ensureLogLevel,
  ensureNonEmptyString,
  ensureNonNegativeInteger,
  ensureNullableString,
  ensurePositiveInteger,
  ensureProjectSource,
  ensureString,
  ensureWhenOthersRunning,
} from "./validation";

function ensureHistorySortKey(
  value: unknown,
  strSourceName: string,
): Dict_History_Options["sortBy"][number]["key"] {
  switch (value) {
    case "scheduler_name":
    case "project_source":
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

function ensureHistorySortOrder(value: unknown, strSourceName: string): "asc" | "desc" {
  if (value === "asc" || value === "desc") {
    return value;
  }
  throw new Error(`${strSourceName} must be 'asc' or 'desc'.`);
}

export function ensureInvokeCommand(value: unknown): TypeExecutorInvokeCommand {
  switch (value) {
    case "openProjectLogFolder":
    case "saveExecutorConfig":
    case "pythonRun":
    case "getPythonEnvironmentNames":
    case "importProjectPackage":
    case "deleteExecutorPackage":
    case "selectProjectNames":
    case "selectProjectVersions":
    case "selectProjectDetail":
    case "updateProjectDetail":
    case "selectProjectBindSchedulers":
    case "deleteProject":
    case "selectSchedulerList":
    case "selectSchedulerDetail":
    case "insertSchedulerDetail":
    case "updateSchedulerDetail":
    case "deleteScheduler":
    case "selectHistoryList":
    case "hasRunningHistory":
    case "openFolder":
    case "selectNewestProjectVersionDetail":
    case "pythonCancel":
    case "selectProjectLogFolder":
    case "cleanLogFoldersByTimeout":
    case "cleanVideosByTimeout":
    case "cleanVideosBySize":
      return value;
    default:
      throw new Error(`Unknown Renderer invoke command: ${String(value)}`);
  }
}

export function ensureRendererLogLevel(value: unknown): TypeRendererLogLevel {
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

export function ensureNoData(value: unknown, strCommand: string): undefined {
  if (value !== undefined) {
    throw new Error(`${strCommand} does not accept request data.`);
  }
  return undefined;
}

export function ensureStringData(value: unknown, strCommand: string): string {
  return ensureString(value, `${strCommand} data`);
}

export function ensurePositiveIntegerData(value: unknown, strCommand: string): number {
  return ensurePositiveInteger(value, `${strCommand} data`);
}

export function ensureNonNegativeNumberData(value: unknown, strCommand: string): number {
  const floatValue = ensureFiniteNumber(value, `${strCommand} data`);
  if (floatValue < 0) {
    throw new Error(`${strCommand} data must be non-negative.`);
  }
  return floatValue;
}

export function ensurePackageRef(value: unknown): { name: string; version: string } {
  const dictValue = ensureExactRecord(value, ["name", "version"], "Package reference");
  return {
    name: ensureNonEmptyString(dictValue.name, "Package reference.name"),
    version: ensureNonEmptyString(dictValue.version, "Package reference.version"),
  };
}

export function ensureProjectRef(value: unknown): { name: string; version: string } {
  const dictValue = ensureExactRecord(value, ["name", "version"], "Project reference");
  return {
    name: ensureNonEmptyString(dictValue.name, "Project reference.name"),
    version: ensureNonEmptyString(dictValue.version, "Project reference.version"),
  };
}

export function ensureProjectRun(value: unknown): DictColumns_Project_Detail_Run {
  const dictValue = ensureExactRecord(
    value,
    [
      "scheduler_name",
      "project_source",
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
    "Project run request",
  );

  return {
    scheduler_name: ensureNullableString(
      dictValue.scheduler_name,
      "Project run request.scheduler_name",
    ),
    project_source: ensureProjectSource(
      dictValue.project_source,
      "Project run request.project_source",
    ),
    id: ensurePositiveInteger(dictValue.id, "Project run request.id"),
    name: ensureNonEmptyString(dictValue.name, "Project run request.name"),
    version: ensureNonEmptyString(dictValue.version, "Project run request.version"),
    python_environment_name: ensureNonEmptyString(
      dictValue.python_environment_name,
      "Project run request.python_environment_name",
    ),
    timeout_min: ensureNonNegativeInteger(
      dictValue.timeout_min,
      "Project run request.timeout_min",
    ),
    builtin_log_level: ensureLogLevel(
      dictValue.builtin_log_level,
      "Project run request.builtin_log_level",
    ),
    builtin_record_video: ensureBoolean(
      dictValue.builtin_record_video,
      "Project run request.builtin_record_video",
    ),
    builtin_stop_shortcut: ensureBoolean(
      dictValue.builtin_stop_shortcut,
      "Project run request.builtin_stop_shortcut",
    ),
    builtin_highlight_ui: ensureBoolean(
      dictValue.builtin_highlight_ui,
      "Project run request.builtin_highlight_ui",
    ),
    custom_prj_args: ensureCustomProjectArgs(
      dictValue.custom_prj_args,
      "Project run request.custom_prj_args",
    ),
  };
}

export function ensureProjectUpdate(value: unknown): DictColumns_Project_Detail_ToUpdate {
  const dictValue = ensureExactRecord(
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
    ],
    "Project update request",
  );

  return {
    id: ensurePositiveInteger(dictValue.id, "Project update request.id"),
    name: ensureNonEmptyString(dictValue.name, "Project update request.name"),
    version: ensureNonEmptyString(dictValue.version, "Project update request.version"),
    description: ensureString(dictValue.description, "Project update request.description"),
    version_summary: ensureString(
      dictValue.version_summary,
      "Project update request.version_summary",
    ),
    python_environment_name: ensureNonEmptyString(
      dictValue.python_environment_name,
      "Project update request.python_environment_name",
    ),
    timeout_min: ensureNonNegativeInteger(
      dictValue.timeout_min,
      "Project update request.timeout_min",
    ),
    builtin_log_level: ensureLogLevel(
      dictValue.builtin_log_level,
      "Project update request.builtin_log_level",
    ),
    builtin_record_video: ensureBinaryInteger(
      dictValue.builtin_record_video,
      "Project update request.builtin_record_video",
    ),
    builtin_stop_shortcut: ensureBinaryInteger(
      dictValue.builtin_stop_shortcut,
      "Project update request.builtin_stop_shortcut",
    ),
    builtin_highlight_ui: ensureBinaryInteger(
      dictValue.builtin_highlight_ui,
      "Project update request.builtin_highlight_ui",
    ),
    custom_prj_args: ensureCustomProjectArgsJson(
      dictValue.custom_prj_args,
      "Project update request.custom_prj_args",
    ),
  };
}

function ensureSchedulerData(
  value: unknown,
  boolIncludeId: boolean,
): DictColumns_Scheduler_Detail_ToInsert | DictColumns_Scheduler_Detail_ToUpdate {
  const arrExpectedKey = [
    "name",
    "project_source",
    "project_id",
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

  const dictBase: DictColumns_Scheduler_Detail_ToInsert = {
    name: ensureNonEmptyString(dictValue.name, "Schedule request.name"),
    project_source: ensureProjectSource(
      dictValue.project_source,
      "Schedule request.project_source",
    ),
    project_id: ensurePositiveInteger(dictValue.project_id, "Schedule request.project_id"),
    cron: ensureNonEmptyString(dictValue.cron, "Schedule request.cron"),
    when_others_running: ensureWhenOthersRunning(
      dictValue.when_others_running,
      "Schedule request.when_others_running",
    ),
    period_start_ms: intPeriodStartMs,
    period_end_ms: intPeriodEndMs,
    enable: ensureBinaryInteger(dictValue.enable, "Schedule request.enable"),
    timeout_min: ensureNonNegativeInteger(
      dictValue.timeout_min,
      "Schedule request.timeout_min",
    ),
    builtin_log_level: ensureLogLevel(
      dictValue.builtin_log_level,
      "Schedule request.builtin_log_level",
    ),
    builtin_record_video: ensureBinaryInteger(
      dictValue.builtin_record_video,
      "Schedule request.builtin_record_video",
    ),
    builtin_stop_shortcut: ensureBinaryInteger(
      dictValue.builtin_stop_shortcut,
      "Schedule request.builtin_stop_shortcut",
    ),
    builtin_highlight_ui: ensureBinaryInteger(
      dictValue.builtin_highlight_ui,
      "Schedule request.builtin_highlight_ui",
    ),
    custom_prj_args: ensureCustomProjectArgsJson(
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

export function ensureSchedulerInsert(
  value: unknown,
): DictColumns_Scheduler_Detail_ToInsert {
  return ensureSchedulerData(value, false);
}

export function ensureSchedulerUpdate(
  value: unknown,
): DictColumns_Scheduler_Detail_ToUpdate {
  const dictValue = ensureSchedulerData(value, true);
  if (!("id" in dictValue)) {
    throw new Error("Schedule update request is missing id.");
  }
  return dictValue;
}

export function ensureHistoryOptions(value: unknown): Dict_History_Options {
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
    const strKey = ensureHistorySortKey(
      dictSort.key,
      `Run History options.sortBy[${intIndex}].key`,
    );
    const strOrder = ensureHistorySortOrder(
      dictSort.order,
      `Run History options.sortBy[${intIndex}].order`,
    );
    return { key: strKey, order: strOrder };
  });

  const dictSearch = ensureExactRecord(
    dictValue.search,
    ["scheduler_name", "project_source", "project_name", "project_version", "status"],
    "Run History options.search",
  );

  const strProjectSource =
    dictSearch.project_source === null
      ? null
      : ensureProjectSource(
          dictSearch.project_source,
          "Run History options.search.project_source",
        );

  const status =
    dictSearch.status === null
      ? null
      : ensureHistoryStatus(dictSearch.status, "Run History options.search.status");

  return {
    page: ensurePositiveInteger(dictValue.page, "Run History options.page"),
    itemsPerPage: ensurePositiveInteger(
      dictValue.itemsPerPage,
      "Run History options.itemsPerPage",
    ),
    sortBy: arrSortBy,
    search: {
      scheduler_name: ensureString(
        dictSearch.scheduler_name,
        "Run History options.search.scheduler_name",
      ),
      project_source: strProjectSource,
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
