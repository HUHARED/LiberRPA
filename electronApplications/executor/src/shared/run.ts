// FileName: run.ts

export enum RunSource {
  Local = "local",
  Console = "console",
}

export interface RunOutputs {
  status: "complete" | "partial" | "unavailable";
  values: [string, unknown][] | null;
  unavailableKeys: string[];
  reason: string;
}

export interface RunDetails {
  source: RunSource;
  run_id: string;
  job_id: string;
  attempt: number;
  inputs: Record<string, unknown>;
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

export type RunTerminalStatus = Exclude<RunStatus, RunStatus.Running | RunStatus.Unknown>;

export interface Dict_RunHistory_Item {
  id: number;
  source: RunSource;
  attempt: number;
  schedule_name: string | null;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  run_ended_at_ms: number | null;
  status: RunStatus;
}

export interface Dict_RunHistory_Search {
  schedule_name: string;
  project_name: string;
  project_version: string;
  status: RunStatus | null;
}

export interface Dict_RunHistory_Options {
  page: number;
  itemsPerPage: number;
  sortBy: {
    key:
      | "schedule_name"
      | "project_name"
      | "project_version"
      | "python_environment_name"
      | "run_started_at_ms"
      | "run_ended_at_ms"
      | "status";
    order: "asc" | "desc";
  }[];
  // Vuetify also sends an unused groupBy value.
  search: Dict_RunHistory_Search;
}

export interface Dict_RunHistory_Page {
  rows: Dict_RunHistory_Item[];
  total: number;
}

export enum RunQueueState {
  Pending = "pending",
  WaitingRetry = "waiting_retry",
  Waiting = "waiting",
  Starting = "starting",
  Running = "running",
  Stopping = "stopping",
}

export interface RunQueueItem {
  queue_id: string;
  source: RunSource;
  schedule_name: string | null;
  project_name: string;
  project_version: string;
  estimated_run_at_ms: number | null;
  started_at_ms: number | null;
  history_id: number | null;
  state: RunQueueState;
}
