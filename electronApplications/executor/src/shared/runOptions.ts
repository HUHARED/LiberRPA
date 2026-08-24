// FileName: runOptions.ts

export type TypeColumns_LogLevel =
  | "VERBOSE"
  | "DEBUG"
  | "INFO"
  | "WARNING"
  | "ERROR"
  | "CRITICAL";

export type TypeCustomProjectArgs = [string, unknown][];

export type TypeColumns_RunOptions_NeedConvert =
  | "builtin_record_video"
  | "builtin_stop_shortcut"
  | "builtin_highlight_ui"
  | "custom_prj_args";

export interface DictColumns_RunOptions_NeedConvert_DB {
  builtin_record_video: 0 | 1;
  builtin_stop_shortcut: 0 | 1;
  builtin_highlight_ui: 0 | 1;
  custom_prj_args: string;
}

export interface DictColumns_RunOptions_NeedConvert_TS {
  builtin_record_video: boolean;
  builtin_stop_shortcut: boolean;
  builtin_highlight_ui: boolean;
  custom_prj_args: TypeCustomProjectArgs;
}

export interface DictColumns_RunOptions_TimeoutAndLog {
  timeout_min: number;
  builtin_log_level: TypeColumns_LogLevel;
}

export interface DictColumns_RunOptions_ExecutionEnvironment {
  python_environment_name: string;
}
