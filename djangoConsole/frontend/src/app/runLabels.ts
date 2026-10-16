// FileName: runLabels.ts

import {
  ARR_CONFLICT_POLICY,
  ARR_PRIORITY,
  type ConflictPolicy,
  type Priority,
} from "@/api/runSettings";
import type { PackagePreparationState, PackageUploadState } from "@/api/packages";
import { RunStatus, type JobSource, JobState, type RunEventKind } from "@/api/runs";

export const CONFLICT_POLICY_LABELS: Record<ConflictPolicy, string> = {
  skip: "Skip This Run",
  wait: "Wait",
  concurrent: "Run Concurrently",
};
export const ARR_CONFLICT_POLICY_OPTION = ARR_CONFLICT_POLICY.map((value) => ({
  value,
  title: CONFLICT_POLICY_LABELS[value],
}));
export const PRIORITY_LABELS: Record<Priority, string> = {
  high: "High",
  normal: "Normal",
  low: "Low",
};
export const ARR_PRIORITY_OPTION = ARR_PRIORITY.map((value) => ({
  value,
  title: PRIORITY_LABELS[value],
}));

export const PACKAGE_UPLOAD_LABELS: Record<PackageUploadState, string> = {
  receiving: "Receiving",
  completed: "Completed",
  failed: "Failed",
  expired: "Expired",
  canceled: "Canceled",
};
export const PACKAGE_PREPARATION_LABELS: Record<PackagePreparationState, string> = {
  pending: "Pending",
  preparing: "Preparing",
  ready: "Ready",
  failed: "Failed",
};

export const JOB_SOURCE_LABELS: Record<JobSource, string> = {
  manual: "Manual",
  api: "API",
  schedule: "Schedule",
};
export const JOB_STATE_LABELS: Record<JobState, string> = {
  waiting: "Waiting",
  preparing: "Preparing",
  starting: "Starting",
  running: "Running",
  stopping: "Stopping",
  waiting_retry: "Waiting for Retry",
  needs_review: "Needs Review",
  finished: "Finished",
};
export const JOB_STATE_COLORS: Record<JobState, string> = {
  [JobState.Waiting]: "warning",
  [JobState.Preparing]: "info",
  [JobState.Starting]: "info",
  [JobState.Running]: "success",
  [JobState.Stopping]: "warning",
  [JobState.WaitingRetry]: "info",
  [JobState.NeedsReview]: "warning",
  [JobState.Finished]: "inactive",
};
export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  running: "Running",
  completed: "Completed",
  error: "Error",
  canceled: "Canceled",
  timed_out: "Timed Out",
  interrupted: "Interrupted",
};
export const RUN_STATUS_COLORS: Record<RunStatus, string> = {
  [RunStatus.Running]: "success",
  [RunStatus.Completed]: "inactive",
  [RunStatus.Error]: "error",
  [RunStatus.Canceled]: "warning",
  [RunStatus.TimedOut]: "run-timeout",
  [RunStatus.Interrupted]: "run-interrupted",
};
export const RUN_EVENT_LABELS: Record<RunEventKind, string> = {
  started: "Started",
  ended: "Ended",
  preparation_failed: "Preparation Failed",
  not_started: "Not Started",
  unknown: "Unknown",
  recording: "Recording",
};
