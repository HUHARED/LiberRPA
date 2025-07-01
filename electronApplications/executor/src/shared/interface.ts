export interface DictBasicConfig {
  outputLogPath: string;
  localServerPort: number;
  uiAnalyzerTheme: "light" | "dark";
  uiAnalyzerMinimizeWindow: boolean;
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
  data?: any;
}

/* Common type for database. */

interface DictColumns_Base {
  id: number;
  created_at: string;
  updated_at: string;
}

type TypeColumns_ModifyTime = "created_at" | "updated_at";

type TypeColumns_LogLevel = "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

type TypeColumns_Project_NeedConvert =
  | "buildin_record_video"
  | "buildin_stop_shortcut"
  | "buildin_highlight_ui"
  | "custom_prj_args";

interface DictColumns_Project_NeedConvert_DB {
  buildin_record_video: 0 | 1;
  buildin_stop_shortcut: 0 | 1;
  buildin_highlight_ui: 0 | 1;
  custom_prj_args: string;
}

interface DictColumns_Project_NeedConvert_TS {
  buildin_record_video: boolean;
  buildin_stop_shortcut: boolean;
  buildin_highlight_ui: boolean;
  custom_prj_args: string[][];
}

interface DictColumns_Project_TimeoutAndLog {
  timeout_min: number;
  buildin_log_level: TypeColumns_LogLevel;
}

/* Project Local Package */

export interface DictColumns_Project_Detail_DB
  extends DictColumns_Base,
    DictColumns_Project_NeedConvert_DB,
    DictColumns_Project_TimeoutAndLog {
  name: string;
  version: string;
  description: string;
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

export type DictColumns_Project_Detail_ToUpdate = Omit<
  DictColumns_Project_Detail_DB,
  TypeColumns_ModifyTime
>;

export type DictColumns_Project_Detail_Run = Omit<
  DictColumns_Project_Detail,
  TypeColumns_ModifyTime | "description"
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

  // These values will not showed in Task Scheduler list, but queueStore needs them.
  period_start: string;
  period_end: string;
  when_others_running: "cancel" | "wait" | "run";
}

export type DictColumns_Scheduler_ListItem = Omit<
  DictColumns_Scheduler_ListItem_DB,
  "enable"
> & {
  enable: boolean;
};

export interface DictColumns_Scheduler_Detail_DB
  extends DictColumns_Base,
    DictColumns_Scheduler_ListItem_DB,
    DictColumns_Project_NeedConvert_DB,
    DictColumns_Project_TimeoutAndLog {
  project_id: number;
  when_others_running: "cancel" | "wait" | "run";
  period_start: string;
  period_end: string;
}

export type DictColumns_Scheduler_Detail = Omit<
  DictColumns_Scheduler_Detail_DB,
  TypeColumns_Project_NeedConvert | "enable"
> &
  DictColumns_Base &
  DictColumns_Project_NeedConvert_TS & {
    enable: boolean;
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
  run_start: string;
  status: "running" | "cancel";
  log_path: string;
}

export interface DictColumns_History_ToUpdate {
  id: number;
  run_end: string;
  status: "completed" | "error" | "cancel" | "timeout";
}

export interface DictColumns_History_ListItem_DB {
  id: number;
  schduler_name: string | null;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  run_start: string;
  run_end: string | null;
  status: "running" | "completed" | "error" | "cancel" | "timeout";
  log_path: string;
}

export interface Dict_History_Search {
  scheduler_name: string;
  project_source: "local" | "console" | null;
  project_name: string;
  project_version: string;
  status: "running" | "completed" | "error" | "cancel" | "timeout" | null;
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
      | "run_start"
      | "run_end"
      | "status";
    order: "asc" | "desc";
  }[];
  // And a useless value: groupBy.
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
  estimated_run_time: string;
  waiting: boolean;
}
