// FileName: runs.ts

import { requestApi } from "./client";
import {
  isDateString,
  isNonnegativeInteger,
  isRecord,
  parsePaginationResponse,
  rejectInvalidResponse,
} from "./responses";
import type { PaginationResponse } from "./generated/browserApi";
import {
  ARR_LOG_LEVEL,
  type JsonValue,
  type LogLevel,
  type RunSettings,
  type RunSnapshot,
} from "./runOptions";

export const ARR_JOB_STATE = [
  "waiting",
  "preparing",
  "starting",
  "running",
  "stopping",
  "waiting_retry",
  "needs_review",
] as const;
export const ARR_RUN_RESULT = [
  "running",
  "completed",
  "error",
  "canceled",
  "timed_out",
  "interrupted",
] as const;
export type JobState = (typeof ARR_JOB_STATE)[number] | "finished";
export type RunResult = (typeof ARR_RUN_RESULT)[number];
export const ARR_JOB_SOURCE = ["manual", "api", "schedule"] as const;
export const ARR_OUTPUTS_STATUS = [
  "waiting",
  "complete",
  "partial",
  "unavailable",
] as const;
export interface JobInfo {
  id: string;
  request_id: string;
  department_id: string;
  source: (typeof ARR_JOB_SOURCE)[number];
  schedule_id: string | null;
  schedule_name: string;
  scheduled_at: string | null;
  project_name: string;
  version: string;
  package_id: string | null;
  target_type: "executor" | "group";
  target_id: string;
  target_name: string;
  executor_id: string | null;
  executor_name: string | null;
  priority: "high" | "normal" | "low";
  state: JobState;
  reason: string;
  queued_at: string;
  retry_at: string | null;
  closed_at: string | null;
  ended_at: string | null;
  can_cancel: boolean;
  can_stop: boolean;
  can_close: boolean;
}
export interface JobEvent {
  kind: string;
  occurred_at: string;
  reason: string;
}
export interface RunInfo {
  id: string;
  job_id: string;
  department_id: string;
  schedule_name: string;
  project_name: string;
  version: string;
  executor_id: string;
  executor_name: string;
  account_name: string;
  computer: string;
  attempt: number;
  started_at: string;
  ended_at: string | null;
  result: RunResult;
  reason: string;
  outputs_status: "waiting" | "complete" | "partial" | "unavailable";
  can_stop: boolean;
}
export interface JobDetails extends JobInfo {
  inputs: RunSnapshot;
  runs: RunInfo[];
  events: JobEvent[];
}
export interface RecordingInfo {
  status?: "recording" | "processing" | "ready" | "unavailable";
  reason?: string;
  videoSizeBytes?: number | null;
  subtitleSizeBytes?: number | null;
}
export interface RunFileAvailability {
  available: boolean;
  reason: string;
  size_bytes: number | null;
}
export interface RunDetails extends RunInfo {
  inputs: RunSnapshot;
  outputs: Record<string, JsonValue> | null;
  outputs_reason: string;
  outputs_unavailable_keys: string[];
  error_summary: Record<string, JsonValue> | null;
  job: JobInfo;
  other_runs: RunInfo[];
  logs_cleared_at: string | null;
  recording: RecordingInfo;
  files: {
    logs: RunFileAvailability;
    video: RunFileAvailability;
    subtitles: RunFileAvailability;
  };
}
export interface RunFilters {
  departmentIds: string[];
  projectName: string;
  scheduleName: string;
  states: string[];
  executorId: string;
  startedFrom: string;
  startedUntil: string;
}
export interface JobPage extends PaginationResponse {
  jobs: JobInfo[];
}
export interface RunPage extends PaginationResponse {
  runs: RunInfo[];
}
export interface LogEntry {
  log_id: string;
  sequence: number;
  timestamp: string;
  received_at: string;
  level: LogLevel;
  user_name: string;
  machine_name: string;
  process_name: string;
  file_name: string;
  line_no: string;
  project_name: string;
  message_text: string;
  custom_fields: Record<string, string>;
}
export interface LogPage {
  logs: LogEntry[];
  before_cursor: number | null;
  after_cursor: number;
  has_more: boolean;
  cleared: boolean;
  complete: boolean;
}
export function getStateLabel(state: string): string {
  return state === "waiting_retry"
    ? "Waiting for Retry"
    : state
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}
function buildQuery(filters: RunFilters, page: number, isJob: boolean): URLSearchParams {
  const query = new URLSearchParams({ page: String(page) });
  for (const id of filters.departmentIds) query.append("department_id", id);
  for (const state of filters.states) query.append(isJob ? "state" : "result", state);
  for (const [key, value] of [
    ["project_name", filters.projectName],
    ["schedule_name", filters.scheduleName],
    ["executor_id", filters.executorId],
    ["started_from", filters.startedFrom],
    ["started_until", filters.startedUntil],
  ])
    if (value && key) query.set(key, value);
  return query;
}
function isJob(value: unknown): value is JobInfo {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    [...ARR_JOB_STATE, "finished"].some((state) => value.state === state) &&
    ARR_JOB_SOURCE.some((source) => value.source === source) &&
    ["high", "normal", "low"].some((priority) => value.priority === priority) &&
    typeof value.project_name === "string" &&
    typeof value.can_stop === "boolean"
  );
}
function isRun(value: unknown): value is RunInfo {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    ARR_RUN_RESULT.some((result) => value.result === result) &&
    ARR_OUTPUTS_STATUS.some((status) => value.outputs_status === status) &&
    typeof value.project_name === "string" &&
    typeof value.can_stop === "boolean"
  );
}
export async function getJobs(filters: RunFilters, page = 1): Promise<JobPage> {
  const result = await requestApi(`/jobs/?${buildQuery(filters, page, true)}`);
  if (!isRecord(result) || !Array.isArray(result.jobs) || !result.jobs.every(isJob))
    return rejectInvalidResponse();
  return { jobs: result.jobs, ...parsePaginationResponse(result) };
}
export async function getRuns(filters: RunFilters, page = 1): Promise<RunPage> {
  const result = await requestApi(`/runs/?${buildQuery(filters, page, false)}`);
  if (!isRecord(result) || !Array.isArray(result.runs) || !result.runs.every(isRun))
    return rejectInvalidResponse();
  return { runs: result.runs, ...parsePaginationResponse(result) };
}
export async function getJob(id: string): Promise<JobDetails> {
  const result = await requestApi(`/jobs/${encodeURIComponent(id)}/`);
  if (
    !isRecord(result) ||
    !isRecord(result.job) ||
    !isRecord(result.job.inputs) ||
    !isJob(result.job)
  )
    return rejectInvalidResponse();
  return result.job as unknown as JobDetails;
}
export async function getRun(id: string): Promise<RunDetails> {
  const result = await requestApi(`/runs/${encodeURIComponent(id)}/`);
  if (
    !isRecord(result) ||
    !isRecord(result.run) ||
    !isRecord(result.run.inputs) ||
    !isRun(result.run)
  )
    return rejectInvalidResponse();
  return result.run as unknown as RunDetails;
}
export async function createJobs(
  packageId: string,
  executorIds: string[],
  groupId: string | null,
  settings: RunSettings,
  requestId: string,
): Promise<void> {
  await requestApi("/jobs/", {
    method: "POST",
    body: {
      request_id: requestId,
      package_id: packageId,
      executor_ids: executorIds,
      group_id: groupId,
      settings,
    },
  });
}
export async function controlJob(
  id: string,
  action: "cancel" | "stop" | "close",
): Promise<void> {
  await requestApi(`/jobs/${encodeURIComponent(id)}/control/`, {
    method: "POST",
    body: { action },
  });
}
export async function stopRun(id: string): Promise<void> {
  await requestApi(`/runs/${encodeURIComponent(id)}/stop/`, { method: "POST", body: {} });
}
export async function getRerun(id: string): Promise<{
  package_id: string;
  executor_ids: string[];
  group_id: string | null;
  original_job_active: boolean;
}> {
  const result = await requestApi(`/runs/${encodeURIComponent(id)}/rerun/`);
  if (
    !isRecord(result) ||
    typeof result.package_id !== "string" ||
    !Array.isArray(result.executor_ids)
  )
    return rejectInvalidResponse();
  return result as unknown as {
    package_id: string;
    executor_ids: string[];
    group_id: string | null;
    original_job_active: boolean;
  };
}
function isLogEntry(value: unknown): value is LogEntry {
  return (
    isRecord(value) &&
    typeof value.log_id === "string" &&
    isNonnegativeInteger(value.sequence) &&
    isDateString(value.timestamp) &&
    isDateString(value.received_at) &&
    ARR_LOG_LEVEL.some((level) => value.level === level) &&
    typeof value.user_name === "string" &&
    typeof value.machine_name === "string" &&
    typeof value.process_name === "string" &&
    typeof value.file_name === "string" &&
    typeof value.line_no === "string" &&
    /^(0|[1-9]\d*)$/.test(value.line_no) &&
    typeof value.project_name === "string" &&
    typeof value.message_text === "string" &&
    isRecord(value.custom_fields) &&
    Object.values(value.custom_fields).every((field) => typeof field === "string")
  );
}
export async function getRunLogs(
  id: string,
  cursor: { before?: number; after?: number } = {},
): Promise<LogPage> {
  const query = new URLSearchParams(
    Object.entries(cursor).map(([key, value]) => [key, String(value)]),
  );
  const result = await requestApi(`/runs/${encodeURIComponent(id)}/logs/?${query}`);
  if (
    !isRecord(result) ||
    !Array.isArray(result.logs) ||
    !result.logs.every(isLogEntry) ||
    !(result.before_cursor === null || isNonnegativeInteger(result.before_cursor)) ||
    !isNonnegativeInteger(result.after_cursor) ||
    typeof result.has_more !== "boolean" ||
    typeof result.cleared !== "boolean" ||
    typeof result.complete !== "boolean"
  )
    return rejectInvalidResponse();
  return {
    logs: result.logs,
    before_cursor: result.before_cursor,
    after_cursor: result.after_cursor,
    has_more: result.has_more,
    cleared: result.cleared,
    complete: result.complete,
  };
}
export async function clearRunLogs(ids: string[]): Promise<{
  cleared: number;
  skipped: { id: string; reason: string }[];
  failed: { id: string; reason: string }[];
}> {
  const result = await requestApi("/runs/clear-logs/", {
    method: "POST",
    body: { run_ids: ids },
  });
  if (
    !isRecord(result) ||
    typeof result.cleared !== "number" ||
    !Array.isArray(result.skipped) ||
    !Array.isArray(result.failed)
  )
    return rejectInvalidResponse();
  return result as unknown as {
    cleared: number;
    skipped: { id: string; reason: string }[];
    failed: { id: string; reason: string }[];
  };
}
export async function downloadRunFile(
  id: string,
  kind: "logs" | "video" | "subtitles",
): Promise<void> {
  const result = await requestApi(`/runs/${encodeURIComponent(id)}/files/`, {
    method: "POST",
    body: { kind },
  });
  if (
    !isRecord(result) ||
    typeof result.download_url !== "string" ||
    !/^\/api\/run-files\/[0-9a-f-]+\/$/i.test(result.download_url)
  )
    return rejectInvalidResponse();
  const link = document.createElement("a");
  link.href = result.download_url;
  link.download = "";
  link.click();
}

export interface RunDepartmentInfo {
  id: string;
  name: string;
  path: string;
  deleted_at: string | null;
}
export async function getRunDepartments(): Promise<RunDepartmentInfo[]> {
  const result = await requestApi("/runs/departments/");
  if (
    !isRecord(result) ||
    !Array.isArray(result.departments) ||
    !result.departments.every(
      (entry: unknown) =>
        isRecord(entry) && typeof entry.id === "string" && typeof entry.path === "string",
    )
  )
    return rejectInvalidResponse();
  return result.departments as RunDepartmentInfo[];
}
