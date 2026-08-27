// FileName: runOptions.ts

export type Str_LogLevel = "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type Arr_CustomProjectArgs = [string, unknown][];

export interface Dict_RunOptions {
  timeout_min: number;

  builtin_log_level: Str_LogLevel;
  builtin_record_video: boolean;
  builtin_stop_shortcut: boolean;
  builtin_highlight_ui: boolean;
  custom_prj_args: Arr_CustomProjectArgs;
}

export interface Dict_PythonEnvironmentSelection {
  python_environment_name: string;
}
