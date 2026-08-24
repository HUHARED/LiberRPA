// FileName: runOptions.ts

export type TypeLogLevel = "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type TypeCustomProjectArgs = [string, unknown][];

export interface DictRunOptions {
  timeout_min: number;
  builtin_log_level: TypeLogLevel;
  builtin_record_video: boolean;
  builtin_stop_shortcut: boolean;
  builtin_highlight_ui: boolean;
  custom_prj_args: TypeCustomProjectArgs;
}

export interface DictPythonEnvironmentSelection {
  python_environment_name: string;
}
