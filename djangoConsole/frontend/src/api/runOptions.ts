// FileName: runOptions.ts

import type { AssetType } from "./generated/browserApi";
import { isRecord } from "./responses";

export type JsonValue =
  null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type ConflictPolicy = "skip" | "wait" | "concurrent";
export type Priority = "high" | "normal" | "low";
export type LogLevel = "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export interface AssetBinding {
  name: string;
  asset_type: AssetType;
}
export interface RunEmailEvent {
  enabled: boolean;
  subject: string;
  body: string;
}
export interface RunEmailConfig {
  recipient_ids: string[];
  on_start: RunEmailEvent;
  on_completed: RunEmailEvent;
  on_error: RunEmailEvent;
}
export interface RunSettings {
  retry_count: number;
  timeout_min: number;
  builtin_log_level: LogLevel;
  builtin_record_video: boolean;
  builtin_stop_shortcut: boolean;
  builtin_highlight_ui: boolean;
  custom_prj_args: [string, JsonValue][];
  custom_arg_assets: (AssetBinding | null)[];
  run_conflict_policy: ConflictPolicy;
  priority: Priority;
  run_email: RunEmailConfig;
}
export interface RunSnapshot extends RunSettings {
  python_environment_name: string;
}
export const ARR_LOG_LEVEL: LogLevel[] = [
  "VERBOSE",
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
];
export const ARR_CONFLICT_POLICY = [
  { title: "Skip This Run", value: "skip" },
  { title: "Wait", value: "wait" },
  { title: "Run Concurrently", value: "concurrent" },
] as const;
export const ARR_PRIORITY = [
  { title: "High", value: "high" },
  { title: "Normal", value: "normal" },
  { title: "Low", value: "low" },
] as const;
export const INT_MAX_TIMEOUT_MIN = 35791;
export function isRunSettings(value: unknown): value is RunSettings {
  return (
    isRecord(value) &&
    Number.isInteger(value.retry_count) &&
    Number.isInteger(value.timeout_min) &&
    ARR_LOG_LEVEL.includes(value.builtin_log_level as LogLevel) &&
    typeof value.builtin_record_video === "boolean" &&
    typeof value.builtin_stop_shortcut === "boolean" &&
    typeof value.builtin_highlight_ui === "boolean" &&
    Array.isArray(value.custom_prj_args) &&
    value.custom_prj_args.every(
      (entry: unknown) =>
        Array.isArray(entry) && entry.length === 2 && typeof entry[0] === "string",
    ) &&
    Array.isArray(value.custom_arg_assets) &&
    ARR_CONFLICT_POLICY.some((entry) => entry.value === value.run_conflict_policy) &&
    ARR_PRIORITY.some((entry) => entry.value === value.priority) &&
    isRecord(value.run_email)
  );
}
export function cloneRunSettings(settings: RunSettings): RunSettings {
  return JSON.parse(JSON.stringify(settings)) as RunSettings;
}
