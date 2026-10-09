// FileName: runOptions.ts

export const INT_MAX_RETRY_COUNT = 3;
export const INT_RETRY_DELAY_MS = 60_000;
// Keep the timeout within the Node.js single-timer delay range.
export const INT_MAX_RUN_TIMEOUT_MIN = 35_791;

export enum LogLevel {
  Verbose = "VERBOSE",
  Debug = "DEBUG",
  Info = "INFO",
  Warning = "WARNING",
  Error = "ERROR",
  Critical = "CRITICAL",
}

export enum RunConflictPolicy {
  Skip = "skip",
  Wait = "wait",
  Concurrent = "concurrent",
}

export type CustomProjectArgs = [string, unknown][];

export interface RunOptions {
  retry_count: number;
  timeout_min: number;

  builtin_log_level: LogLevel;
  builtin_record_video: boolean;
  builtin_stop_shortcut: boolean;
  builtin_highlight_ui: boolean;
  custom_prj_args: CustomProjectArgs;
}

export interface PythonEnvironmentSelection {
  python_environment_name: string;
}
