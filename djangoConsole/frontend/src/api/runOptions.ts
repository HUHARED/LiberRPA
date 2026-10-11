// FileName: runOptions.ts

import type {
  RunConflictPolicy,
  RunPriority,
  RunLogLevel,
  RunEmailSettingsResponse,
  RunSettingsResponse,
  RunSnapshotResponse,
} from "./generated/browserApi";
import { isRecord } from "./responses";

export type { JsonValue } from "./generated/browserApi";
export type ConflictPolicy = RunConflictPolicy;
export type Priority = RunPriority;
export type LogLevel = RunLogLevel;
export type RunEmailConfig = RunEmailSettingsResponse;
export type RunSettings = RunSettingsResponse;
export type RunSnapshot = RunSnapshotResponse;
export const ARR_CONFLICT_POLICY = [
  "skip",
  "wait",
  "concurrent",
] as const satisfies readonly ConflictPolicy[];
export const ARR_PRIORITY = [
  "high",
  "normal",
  "low",
] as const satisfies readonly Priority[];
export const ARR_LOG_LEVEL = [
  "VERBOSE",
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
] as const satisfies readonly LogLevel[];
export const INT_MAX_TIMEOUT_MIN = 35791;
export function isRunSettings(value: unknown): value is RunSettings {
  return (
    isRecord(value) &&
    Number.isInteger(value.max_retry_count) &&
    Number.isInteger(value.timeout_min) &&
    ARR_LOG_LEVEL.some((level) => level === value.builtin_log_level) &&
    typeof value.builtin_record_video === "boolean" &&
    typeof value.builtin_stop_shortcut === "boolean" &&
    typeof value.builtin_highlight_ui === "boolean" &&
    Array.isArray(value.custom_prj_args) &&
    value.custom_prj_args.every(
      (entry: unknown) =>
        Array.isArray(entry) && entry.length === 2 && typeof entry[0] === "string",
    ) &&
    Array.isArray(value.custom_arg_assets) &&
    value.custom_arg_assets.every(
      (binding: unknown) =>
        binding === null ||
        (isRecord(binding) &&
          typeof binding.name === "string" &&
          ["text", "integer", "number", "boolean", "json"].some(
            (type) => type === binding.asset_type,
          )),
    ) &&
    ARR_CONFLICT_POLICY.some((policy) => policy === value.run_conflict_policy) &&
    ARR_PRIORITY.some((priority) => priority === value.priority) &&
    isRecord(value.run_email) &&
    Array.isArray(value.run_email.recipient_ids) &&
    value.run_email.recipient_ids.every((id: unknown) => typeof id === "string") &&
    [
      value.run_email.on_start,
      value.run_email.on_completed,
      value.run_email.on_error,
    ].every(
      (template: unknown) =>
        isRecord(template) &&
        typeof template.enabled === "boolean" &&
        typeof template.subject === "string" &&
        typeof template.body === "string",
    )
  );
}
export function isRunSnapshot(value: unknown): value is RunSnapshot {
  return (
    isRecord(value) &&
    isRunSettings(value) &&
    typeof value.package_id === "string" &&
    typeof value.department_id === "string" &&
    typeof value.project_name === "string" &&
    typeof value.project_version === "string" &&
    typeof value.sha256 === "string" &&
    typeof value.requires_liberrpa === "string" &&
    typeof value.python_environment_name === "string"
  );
}
export function cloneRunSettings(settings: RunSettings): RunSettings {
  return JSON.parse(JSON.stringify(settings)) as RunSettings;
}
