// FileName: interface.ts

export interface DictBasicConfig {
  outputLogPath: string;
  localServerPort: number;
  uiAnalyzerTheme: "light" | "dark";
  uiAnalyzerMinimizeWindow: boolean;
  componentRepositoryPath: string;
}

// Persisted values in Executor.jsonc.
export interface DictExecutorConfig {
  theme: "light" | "dark";
  keepRdpSession: boolean;
  keepRdpSessionWidth: number;
  keepRdpSessionHeight: number;
  logTimeoutEnable: boolean;
  logTimeoutDays: number;
  videoTimeoutEnable: boolean;
  videoTimeoutDays: number;
  videoSizeEnable: boolean;
  videoSizeGB: number;
  // An empty string uses basic.jsonc's Executor outputLogPath.
  projectLogFolderPath: string;
  timezone: string;
}

/* Common database types. */

interface DictColumns_Base_DB {
  id: number;
  created_at_ms: number;
  updated_at_ms: number;
}

type TypeColumns_ModifyTime = "created_at_ms" | "updated_at_ms";

export type TypeColumns_LogLevel =
  | "VERBOSE"
  | "DEBUG"
  | "INFO"
  | "WARNING"
  | "ERROR"
  | "CRITICAL";

export type TypeRunHistoryStatus =
  | "running"
  | "completed"
  | "error"
  | "cancel"
  | "timeout"
  | "interrupted";

type TypeColumns_Project_NeedConvert =
  | "builtin_record_video"
  | "builtin_stop_shortcut"
  | "builtin_highlight_ui"
  | "custom_prj_args";

interface DictColumns_Project_NeedConvert_DB {
  builtin_record_video: 0 | 1;
  builtin_stop_shortcut: 0 | 1;
  builtin_highlight_ui: 0 | 1;
  custom_prj_args: string;
}

export type TypeCustomProjectArgs = [string, unknown][];

interface DictColumns_Project_NeedConvert_TS {
  builtin_record_video: boolean;
  builtin_stop_shortcut: boolean;
  builtin_highlight_ui: boolean;
  custom_prj_args: TypeCustomProjectArgs;
}

interface DictColumns_Project_TimeoutAndLog {
  timeout_min: number;
  builtin_log_level: TypeColumns_LogLevel;
}

interface DictColumns_Project_ExecutionEnvironment {
  python_environment_name: string;
}

/* Project */

export interface DictColumns_Project_Detail_DB
  extends
    DictColumns_Base_DB,
    DictColumns_Project_NeedConvert_DB,
    DictColumns_Project_TimeoutAndLog,
    DictColumns_Project_ExecutionEnvironment {
  name: string;
  version: string;
  description: string;
  version_summary: string;
}

export type DictColumns_Project_Detail = Omit<
  DictColumns_Project_Detail_DB,
  TypeColumns_Project_NeedConvert
> &
  DictColumns_Project_NeedConvert_TS;

export type DictColumns_Project_Detail_ToInsert = Omit<
  DictColumns_Project_Detail_DB,
  "id" | TypeColumns_ModifyTime
>;

export type DictProjectPackageImportResult =
  | { status: "canceled" }
  | {
      status: "projectPackageImported";
      name: string;
      version: string;
      packageFilePath: string;
      installedFolderPath: string;
    };

export type DictColumns_Project_Detail_ToUpdate = Omit<
  DictColumns_Project_Detail_DB,
  TypeColumns_ModifyTime
>;

export type DictProjectRunDetail = Omit<
  DictColumns_Project_Detail,
  TypeColumns_ModifyTime | "description" | "version_summary"
> & {
  schedule_name: string | null;
  project_source: "local" | "console";
};

/* Schedule */

export interface DictColumns_Schedule_ListItem_DB {
  name: string;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  cron: string;
  enable: 0 | 1;

  // These values are not displayed in the Schedule list, but the Scheduler engine needs them.
  period_start_ms: number;
  period_end_ms: number;
  when_others_running: "cancel" | "wait" | "run";
}

export type DictColumns_Schedule_ListItem = Omit<
  DictColumns_Schedule_ListItem_DB,
  "enable"
> & {
  enable: boolean;
};

export interface DictColumns_Schedule_Detail_DB
  extends
    DictColumns_Base_DB,
    DictColumns_Schedule_ListItem_DB,
    DictColumns_Project_NeedConvert_DB,
    DictColumns_Project_TimeoutAndLog,
    DictColumns_Project_ExecutionEnvironment {
  project_id: number;
}

export type DictColumns_Schedule_Detail = Omit<
  DictColumns_Schedule_Detail_DB,
  TypeColumns_Project_NeedConvert | "enable" | "period_start_ms" | "period_end_ms"
> &
  DictColumns_Project_NeedConvert_TS & {
    enable: boolean;
    period_start: string;
    period_end: string;
  };

export type DictColumns_Schedule_Detail_ToUpdate = Omit<
  DictColumns_Schedule_Detail_DB,
  TypeColumns_ModifyTime | "project_name" | "project_version" | "python_environment_name"
>;

export type DictColumns_Schedule_Detail_ToInsert = Omit<
  DictColumns_Schedule_Detail_DB,
  | "id"
  | TypeColumns_ModifyTime
  | "project_name"
  | "project_version"
  | "python_environment_name"
>;

export type DictColumns_Schedule_Detail_BeforeInsert = Omit<
  DictColumns_Schedule_Detail,
  | "id"
  | TypeColumns_ModifyTime
  | "project_id"
  | "project_name"
  | "project_version"
  | "python_environment_name"
> & {
  project_id: number | undefined;
  project_name: string | undefined;
  project_version: string | undefined;
};

/* Run History */

// The SQLite schema keeps the historical scheduler_name column name.
// Runtime-only objects use schedule_name instead.
export interface DictColumns_RunHistory_ToInsert {
  scheduler_name: string | null;
  project_source: "local" | "console";
  project_id: number;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  status: "running";
  log_path: string;
}

export type DictColumns_RunHistory_ToUpdate =
  | {
      id: number;
      run_ended_at_ms: number;
      status: "completed" | "error" | "cancel" | "timeout";
    }
  | {
      id: number;
      run_ended_at_ms: null;
      status: "interrupted";
    };

export interface DictColumns_RunHistory_ListItem_DB {
  id: number;
  scheduler_name: string | null;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  run_ended_at_ms: number | null;
  status: TypeRunHistoryStatus;
  log_path: string;
}

export interface DictRunHistorySearch {
  scheduler_name: string;
  project_source: "local" | "console" | null;
  project_name: string;
  project_version: string;
  status: TypeRunHistoryStatus | null;
}

export interface DictRunHistoryOptions {
  page: number;
  itemsPerPage: number;
  sortBy: {
    key:
      | "scheduler_name"
      | "project_source"
      | "project_name"
      | "project_version"
      | "python_environment_name"
      | "run_started_at_ms"
      | "run_ended_at_ms"
      | "status";
    order: "asc" | "desc";
  }[];
  // Vuetify also sends an unused groupBy value.
  search: DictRunHistorySearch;
}

export interface DictRunHistoryPage {
  rows: DictColumns_RunHistory_ListItem_DB[];
  total: number;
}

/* Run Queue */

export interface DictRunQueueListItem {
  schedule_name: string;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  estimated_run_at_ms: number;
  waiting: boolean;
}
