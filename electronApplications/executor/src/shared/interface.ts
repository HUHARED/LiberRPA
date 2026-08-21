// FileName: interface.ts

export interface DictBasicConfig {
  outputLogPath: string;
  localServerPort: number;
  uiAnalyzerTheme: "light" | "dark";
  uiAnalyzerMinimizeWindow: boolean;
  componentRepositoryPath: string;
}

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
  projectLogFolderPath: string;
  timezone: string;
}

export interface DictInvokeResult {
  success: boolean;
  data?: unknown;
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

export type TypeTaskHistoryStatus =
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

interface DictColumns_Project_NeedConvert_TS {
  builtin_record_video: boolean;
  builtin_stop_shortcut: boolean;
  builtin_highlight_ui: boolean;
  custom_prj_args: string[][];
}

interface DictColumns_Project_TimeoutAndLog {
  timeout_min: number;
  builtin_log_level: TypeColumns_LogLevel;
}

/* Project Local Package */

export interface DictColumns_Project_Detail_DB
  extends
    DictColumns_Base_DB,
    DictColumns_Project_NeedConvert_DB,
    DictColumns_Project_TimeoutAndLog {
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
  "id" | TypeColumns_ModifyTime | "version_summary"
> & {
  version_summary?: string;
};

export type DictColumns_Project_Detail_ToUpdate = Omit<
  DictColumns_Project_Detail_DB,
  TypeColumns_ModifyTime
>;

export type DictColumns_Project_Detail_Run = Omit<
  DictColumns_Project_Detail,
  TypeColumns_ModifyTime | "description" | "version_summary"
> & {
  scheduler_name: string | null;
  project_source: "local" | "console";
};

/* Task Scheduler */

export interface DictColumns_Scheduler_ListItem_DB {
  name: string;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  cron: string;
  enable: 0 | 1;

  // These values are not displayed in the Scheduler list, but Queue needs them.
  period_start_ms: number;
  period_end_ms: number;
  when_others_running: "cancel" | "wait" | "run";
}

export type DictColumns_Scheduler_ListItem = Omit<
  DictColumns_Scheduler_ListItem_DB,
  "enable"
> & {
  enable: boolean;
};

export interface DictColumns_Scheduler_Detail_DB
  extends
    DictColumns_Base_DB,
    DictColumns_Scheduler_ListItem_DB,
    DictColumns_Project_NeedConvert_DB,
    DictColumns_Project_TimeoutAndLog {
  project_id: number;
}

export type DictColumns_Scheduler_Detail = Omit<
  DictColumns_Scheduler_Detail_DB,
  TypeColumns_Project_NeedConvert | "enable" | "period_start_ms" | "period_end_ms"
> &
  DictColumns_Project_NeedConvert_TS & {
    enable: boolean;
    period_start: string;
    period_end: string;
  };

export type DictColumns_Scheduler_Detail_ToUpdate = Omit<
  DictColumns_Scheduler_Detail_DB,
  TypeColumns_ModifyTime | "project_name" | "project_version"
>;

export type DictColumns_Scheduler_Detail_ToInsert = Omit<
  DictColumns_Scheduler_Detail_DB,
  "id" | TypeColumns_ModifyTime | "project_name" | "project_version"
>;

export type DictColumns_Scheduler_Detail_BeforeInsert = Omit<
  DictColumns_Scheduler_Detail,
  "id" | TypeColumns_ModifyTime | "project_id" | "project_name" | "project_version"
> & {
  project_id: number | undefined;
  project_name: string | undefined;
  project_version: string | undefined;
};

/* Task History */

export interface DictColumns_History_ToInsert {
  scheduler_name: string | null;
  project_source: "local" | "console";
  project_id: number;
  project_name: string;
  project_version: string;
  run_started_at_ms: number;
  status: "running";
  log_path: string;
}

export type DictColumns_History_ToUpdate =
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

export interface DictColumns_History_ListItem_DB {
  id: number;
  scheduler_name: string | null;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  run_started_at_ms: number;
  run_ended_at_ms: number | null;
  status: TypeTaskHistoryStatus;
  log_path: string;
}

export interface Dict_History_Search {
  scheduler_name: string;
  project_source: "local" | "console" | null;
  project_name: string;
  project_version: string;
  status: TypeTaskHistoryStatus | null;
}

export interface Dict_History_Options {
  page: number;
  itemsPerPage: number;
  sortBy: {
    key:
      | "scheduler_name"
      | "project_source"
      | "project_name"
      | "project_version"
      | "run_started_at_ms"
      | "run_ended_at_ms"
      | "status";
    order: "asc" | "desc";
  }[];
  // Vuetify also sends an unused groupBy value.
  search: Dict_History_Search;
}

export type Dict_History_Options_Component = Omit<Dict_History_Options, "search"> & {
  search: string;
};

export interface DictColumns_History_ListItem_Limit_DB {
  rows: DictColumns_History_ListItem_DB[];
  total: number;
}

/* Task Queue */

export interface Dict_TaskQueue_ListItem {
  name: string;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  estimated_run_at_ms: number;
  waiting: boolean;
}
