// FileName: runSettings.ts

import type {
  RunConflictPolicy,
  RunPriority,
  RunLogLevel,
  RunEmailSettingsResponse,
  RunSettingsResponse,
  RunSnapshotResponse,
} from "./generated/browserApi";
import {
  ARR_CONFLICT_POLICY,
  ARR_PRIORITY,
  ARR_LOG_LEVEL,
  INT_MAX_RETRY_COUNT,
  INT_MAX_TIMEOUT_MIN,
} from "./generated/browserApi";

export type { JsonValue } from "./generated/browserApi";
export type ConflictPolicy = RunConflictPolicy;
export type Priority = RunPriority;
export type LogLevel = RunLogLevel;
export type RunEmailConfig = RunEmailSettingsResponse;
export type RunSettings = RunSettingsResponse;
export type RunSnapshot = RunSnapshotResponse;
export {
  ARR_CONFLICT_POLICY,
  ARR_PRIORITY,
  ARR_LOG_LEVEL,
  INT_MAX_RETRY_COUNT,
  INT_MAX_TIMEOUT_MIN,
};
export function cloneRunSettings(settings: RunSettings): RunSettings {
  return JSON.parse(JSON.stringify(settings)) as RunSettings;
}
