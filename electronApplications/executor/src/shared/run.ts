// FileName: run.ts

import type {
  RunConflictPolicy,
  RunSettings,
  PythonEnvironmentSelection,
} from "./runSettings";

export enum RunSource {
  Local = "local",
  Console = "console",
}

export enum RunOutputsStatus {
  Complete = "complete",
  Partial = "partial",
  Unavailable = "unavailable",
}

export interface RunOutputs {
  status: RunOutputsStatus;
  values: [string, unknown][] | null;
  unavailableKeys: string[];
  reason: string;
}

export enum RunRecordingStatus {
  Recording = "recording",
  Processing = "processing",
  Ready = "ready",
  Unavailable = "unavailable",
}

export interface RunRecordingInfo {
  status: RunRecordingStatus;
  videoSizeBytes?: number | null;
  subtitleSizeBytes?: number | null;
  reason?: string;
}

export interface ProjectRunConfig extends RunSettings, PythonEnvironmentSelection {
  run_conflict_policy?: RunConflictPolicy;
  schedule_name: string | null;
  local_project_id: number | null;
  project_name: string;
  project_version: string;
}

export interface RunDetails {
  source: RunSource;
  run_id: string;
  job_id: string;
  attempt_number: number;
  snapshot: ProjectRunConfig;
  outputs: RunOutputs;
  error_summary: { type: string; message: string } | null;
}

export enum RunStatus {
  Running = "running",
  Completed = "completed",
  Error = "error",
  Canceled = "canceled",
  TimedOut = "timed_out",
  Interrupted = "interrupted",
  Unknown = "unknown",
}

export type RunEndedStatus = Exclude<RunStatus, RunStatus.Running | RunStatus.Unknown>;

export interface RunHistoryItem {
  id: number;
  source: RunSource;
  attempt_number: number;
  schedule_name: string | null;
  project_name: string;
  project_version: string;
  run_started_at_ms: number;
  run_ended_at_ms: number | null;
  status: RunStatus;
}

export interface RunHistoryFilters {
  schedule_name: string;
  project_name: string;
  project_version: string;
  status: RunStatus | null;
  source: RunSource | null;
}

export interface RunHistoryQueryOptions {
  page: number;
  itemsPerPage: number;
  sortBy: {
    key:
      | "schedule_name"
      | "project_name"
      | "project_version"
      | "run_started_at_ms"
      | "run_ended_at_ms"
      | "status";
    order: "asc" | "desc";
  }[];
  // Vuetify also sends an unused groupBy value.
  search: RunHistoryFilters;
}

export interface RunHistoryPage {
  rows: RunHistoryItem[];
  total: number;
}

export enum JobQueueState {
  Pending = "pending",
  WaitingRetry = "waiting_retry",
  Waiting = "waiting",
  Starting = "starting",
  Running = "running",
  Stopping = "stopping",
}

export interface JobQueueItem {
  queue_id: string;
  source: RunSource;
  schedule_name: string | null;
  project_name: string;
  project_version: string;
  due_at_ms: number | null;
  started_at_ms: number | null;
  history_id: number | null;
  state: JobQueueState;
}
