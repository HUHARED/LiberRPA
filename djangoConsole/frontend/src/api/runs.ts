// FileName: runs.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNonnegativeInteger,
  isDateString,
  isNullableDateString,
  rejectInvalidResponse,
  parsePaginationResponse,
} from "./responses";
import type {
  JobState,
  RunResult,
  JobSource,
  JobControlAction,
  OutputsStatus,
  RunEventKind as RunEventKindValue,
  RunFileKind as RunFileKindValue,
  JobResponse,
  JobDetailsEntryResponse,
  JobListResponse,
  RunResponse,
  RunDetailsEntryResponse,
  RunListResponse,
  RunLogEntryResponse,
  RunLogListResponse,
  RunDepartmentResponse,
  RunRerunResponse,
  RunLogClearResponse,
} from "./generated/browserApi";
import { type RunSettings, ARR_PRIORITY, ARR_LOG_LEVEL, isRunSnapshot } from "./runOptions";

export type { JobState, RunResult, JobSource, JobControlAction };
export type JobInfo = JobResponse;
export type JobDetails = JobDetailsEntryResponse;
export type JobPage = JobListResponse;
export type RunInfo = RunResponse;
export type RunDetails = RunDetailsEntryResponse;
export type RunPage = RunListResponse;
export type LogEntry = RunLogEntryResponse;
export type LogPage = RunLogListResponse;
export type RunDepartmentInfo = RunDepartmentResponse;
export const ARR_JOB_STATE = [
  "waiting",
  "preparing",
  "starting",
  "running",
  "stopping",
  "waiting_retry",
  "needs_review",
] as const satisfies readonly JobState[];
export const ARR_RUN_RESULT = [
  "running",
  "completed",
  "error",
  "canceled",
  "timed_out",
  "interrupted",
] as const satisfies readonly RunResult[];
export const ARR_JOB_SOURCE = [
  "manual",
  "api",
  "schedule",
] as const satisfies readonly JobSource[];
export type RunEventKind = RunEventKindValue;
export const RunEventKind = {
  Started: "started",
  Ended: "ended",
  PreparationFailed: "preparation_failed",
  NotStarted: "not_started",
  Unknown: "unknown",
  Recording: "recording",
} as const satisfies Record<string, RunEventKind>;
export const ARR_OUTPUTS_STATUS = [
  "waiting",
  "complete",
  "partial",
  "unavailable",
] as const satisfies readonly OutputsStatus[];
export type RunFileKind = RunFileKindValue;
export const RunFileKind = {
  Logs: "logs",
  Video: "video",
  Subtitles: "subtitles",
} as const satisfies Record<string, RunFileKind>;

interface WorkFilters {
  departmentIds: string[];
  projectName: string;
  scheduleName: string;
}
export interface JobFilters extends WorkFilters {
  states: JobState[];
}
export interface RunFilters extends WorkFilters {
  results: RunResult[];
  executorId: string;
  startedFrom: string;
  startedUntil: string;
}
function buildQuery(filters: JobFilters | RunFilters, page?: number): URLSearchParams {
  const query = new URLSearchParams();
  if (page !== undefined) query.set("page", String(page));
  for (const id of filters.departmentIds) query.append("department_id", id);
  if ("states" in filters) for (const state of filters.states) query.append("state", state);
  else for (const result of filters.results) query.append("result", result);
  for (const [key, value] of [
    ["project_name", filters.projectName],
    ["schedule_name", filters.scheduleName],
    ["executor_id", "executorId" in filters ? filters.executorId : ""],
    ["started_from", "startedFrom" in filters ? filters.startedFrom : ""],
    ["started_until", "startedUntil" in filters ? filters.startedUntil : ""],
  ])
    if (value && key) query.set(key, value);
  return query;
}
function isJob(value: unknown): value is JobInfo {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.job_request_id === "string" &&
    [...ARR_JOB_STATE, "finished"].some((state) => value.state === state) &&
    ARR_JOB_SOURCE.some((source) => value.source === source) &&
    ARR_PRIORITY.some((priority) => value.priority === priority) &&
    typeof value.project_name === "string" &&
    typeof value.project_version === "string" &&
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
    typeof value.project_version === "string" &&
    isNonnegativeInteger(value.attempt_number) &&
    value.attempt_number > 0 &&
    typeof value.computer_name === "string" &&
    typeof value.can_rerun === "boolean" &&
    typeof value.can_stop === "boolean"
  );
}
export async function getJobs(filters: JobFilters, page = 1): Promise<JobPage> {
  const result = await requestApi(`/jobs/?${buildQuery(filters, page)}`);
  if (!isRecord(result) || !Array.isArray(result.jobs) || !result.jobs.every(isJob))
    return rejectInvalidResponse();
  return { jobs: result.jobs, ...parsePaginationResponse(result) };
}
export async function getRuns(filters: RunFilters, page = 1): Promise<RunPage> {
  const result = await requestApi(`/runs/?${buildQuery(filters, page)}`);
  if (!isRecord(result) || !Array.isArray(result.runs) || !result.runs.every(isRun))
    return rejectInvalidResponse();
  return { runs: result.runs, ...parsePaginationResponse(result) };
}
export async function getMatchingRunIds(filters: RunFilters): Promise<string[]> {
  const result = await requestApi(`/runs/selection/?${buildQuery(filters)}`);
  if (
    !isRecord(result) ||
    !Array.isArray(result.run_ids) ||
    !result.run_ids.every((id: unknown) => typeof id === "string")
  )
    return rejectInvalidResponse();
  return result.run_ids;
}
export async function getJob(id: string): Promise<JobDetails> {
  const result = await requestApi(`/jobs/${encodeURIComponent(id)}/`);
  if (
    !isRecord(result) ||
    !isRecord(result.job) ||
    !isRunSnapshot(result.job.run_snapshot) ||
    !isJob(result.job) ||
    !Array.isArray(result.job.runs) ||
    !result.job.runs.every(isRun) ||
    !Array.isArray(result.job.events) ||
    !result.job.events.every(
      (event) =>
        isRecord(event) &&
        Object.values(RunEventKind).some((kind) => kind === event.kind) &&
        isDateString(event.occurred_at) &&
        typeof event.reason === "string",
    )
  )
    return rejectInvalidResponse();
  return result.job as unknown as JobDetails;
}
export async function getRun(id: string): Promise<RunDetails> {
  const result = await requestApi(`/runs/${encodeURIComponent(id)}/`);
  if (
    !isRecord(result) ||
    !isRecord(result.run) ||
    typeof result.run.department_path !== "string" ||
    result.run.department_path.length === 0 ||
    !isNullableDateString(result.run.department_deleted_at) ||
    !isRunSnapshot(result.run.run_snapshot) ||
    !isRun(result.run) ||
    !isJob(result.run.job) ||
    !Array.isArray(result.run.other_runs) ||
    !result.run.other_runs.every(isRun) ||
    !isRecord(result.run.recording) ||
    typeof result.run.outputs_reason !== "string" ||
    !Array.isArray(result.run.outputs_unavailable_keys) ||
    !result.run.outputs_unavailable_keys.every((key: unknown) => typeof key === "string") ||
    (result.run.outputs_status === "complete" || result.run.outputs_status === "partial"
      ? !Array.isArray(result.run.outputs) ||
        !result.run.outputs.every(
          (entry: unknown) =>
            Array.isArray(entry) && entry.length === 2 && typeof entry[0] === "string",
        )
      : result.run.outputs !== null)
  )
    return rejectInvalidResponse();
  const dictFiles = result.run.files;
  if (
    !isRecord(dictFiles) ||
    !Object.values(RunFileKind).every((kind) => {
      const availability = dictFiles[kind];
      return (
        isRecord(availability) &&
        typeof availability.available === "boolean" &&
        typeof availability.reason === "string" &&
        (availability.size_bytes === null || isNonnegativeInteger(availability.size_bytes))
      );
    })
  )
    return rejectInvalidResponse();
  return result.run as unknown as RunDetails;
}
export async function createJobs(
  packageId: string,
  executorIds: string[],
  groupId: string | null,
  settings: RunSettings,
  clientRequestId: string,
): Promise<void> {
  const result = await requestApi("/jobs/", {
    method: "POST",
    body: {
      request_id: clientRequestId,
      package_id: packageId,
      executor_ids: executorIds,
      group_id: groupId,
      settings,
    },
  });
  if (
    !isRecord(result) ||
    result.request_id !== clientRequestId ||
    typeof result.job_request_id !== "string" ||
    !Array.isArray(result.jobs) ||
    result.jobs.length === 0 ||
    !result.jobs.every(
      (job: unknown) => isJob(job) && job.job_request_id === result.job_request_id,
    )
  )
    return rejectInvalidResponse();
}
export async function controlJob(id: string, action: JobControlAction): Promise<void> {
  await requestApi(`/jobs/${encodeURIComponent(id)}/control/`, {
    method: "POST",
    body: { action },
  });
}
export async function stopRun(id: string): Promise<void> {
  await requestApi(`/runs/${encodeURIComponent(id)}/stop/`, { method: "POST", body: {} });
}
export async function getRerun(id: string): Promise<RunRerunResponse> {
  const result = await requestApi(`/runs/${encodeURIComponent(id)}/rerun/`);
  if (
    !isRecord(result) ||
    typeof result.package_id !== "string" ||
    !Array.isArray(result.executor_ids) ||
    !result.executor_ids.every((id: unknown) => typeof id === "string") ||
    !(result.group_id === null || typeof result.group_id === "string") ||
    typeof result.original_job_active !== "boolean"
  )
    return rejectInvalidResponse();
  return result as unknown as RunRerunResponse;
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
export async function clearRunLogs(ids: string[]): Promise<RunLogClearResponse> {
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
  return result as unknown as RunLogClearResponse;
}
export async function downloadRunFile(id: string, kind: RunFileKind): Promise<void> {
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
