// FileName: runs.ts

import { downloadFile } from "@/app/files";

import { requestApi } from "./client";
import { isRecord, isNonnegativeInteger, rejectInvalidResponse } from "./responses";
import {
  JobState,
  RunStatus,
  OutputsStatus,
  type RunEventKind,
  type RunFileKind,
  type JobSource,
  type JobControlAction,
  type RecordingStatus,
  type JobResponse,
  type JobDetailsResponse,
  type JobDetailsEntryResponse,
  type JobListResponse,
  type JobCreationResponse,
  type RunResponse,
  type RunDetailsResponse,
  type RunDetailsEntryResponse,
  type RunListResponse,
  type RunLogEntryResponse,
  type RunLogListResponse,
  type RunDepartmentResponse,
  type RunDepartmentListResponse,
  type RunRerunResponse,
  type RunLogClearResponse,
} from "./generated/browserApi";
import type { RunSettings } from "./runSettings";

export type {
  JobState,
  RunStatus,
  JobSource,
  JobControlAction,
  OutputsStatus,
  RecordingStatus,
  RunEventKind,
  RunFileKind,
};
export type JobInfo = JobResponse;
export type JobDetails = JobDetailsEntryResponse;
export type JobPage = JobListResponse;
export type RunInfo = RunResponse;
export type RunDetails = RunDetailsEntryResponse;
export type RunPage = RunListResponse;
export type LogEntry = RunLogEntryResponse;
export type LogPage = RunLogListResponse;
export type RunDepartmentInfo = RunDepartmentResponse;
export const ARR_ACTIVE_JOB_STATE = Object.values(JobState).filter(
  (state) => state !== JobState.Finished,
);
export const ARR_RUN_STATUS = Object.values(RunStatus);
export const ARR_OUTPUTS_STATUS = Object.values(OutputsStatus);

interface WorkFilters {
  departmentIds: string[];
  projectName: string;
  scheduleName: string;
}
export interface JobFilters extends WorkFilters {
  states: JobState[];
}
export interface RunFilters extends WorkFilters {
  statuses: RunStatus[];
  executorId: string;
  startedFrom: string;
  startedUntil: string;
}
function buildQuery(filters: JobFilters | RunFilters, page?: number): URLSearchParams {
  const query = new URLSearchParams();
  if (page !== undefined) query.set("page", String(page));
  for (const id of filters.departmentIds) query.append("department_id", id);
  if ("states" in filters) for (const state of filters.states) query.append("state", state);
  else for (const status of filters.statuses) query.append("status", status);
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
export async function getJobs(filters: JobFilters, page = 1): Promise<JobPage> {
  return requestApi<JobListResponse>(`/jobs/?${buildQuery(filters, page)}`);
}
export async function getRuns(filters: RunFilters, page = 1): Promise<RunPage> {
  return requestApi<RunListResponse>(`/runs/?${buildQuery(filters, page)}`);
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
  const result = await requestApi<JobDetailsResponse>(`/jobs/${encodeURIComponent(id)}/`);
  return result.job;
}
export async function getRun(id: string): Promise<RunDetails> {
  const result = await requestApi<RunDetailsResponse>(`/runs/${encodeURIComponent(id)}/`);
  return result.run;
}
export async function createJobs(
  packageId: string,
  executorIds: string[],
  groupId: string | null,
  settings: RunSettings,
  clientRequestId: string,
): Promise<JobCreationResponse> {
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
      (job: unknown) =>
        isRecord(job) &&
        typeof job.id === "string" &&
        job.job_request_id === result.job_request_id,
    )
  )
    return rejectInvalidResponse();
  return result as unknown as JobCreationResponse;
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
    !result.logs.every(
      (entry: unknown) =>
        isRecord(entry) &&
        typeof entry.log_id === "string" &&
        isNonnegativeInteger(entry.sequence),
    ) ||
    !(result.before_cursor === null || isNonnegativeInteger(result.before_cursor)) ||
    !isNonnegativeInteger(result.after_cursor) ||
    typeof result.has_more !== "boolean" ||
    typeof result.cleared !== "boolean" ||
    typeof result.complete !== "boolean" ||
    typeof result.unavailable_reason !== "string"
  )
    return rejectInvalidResponse();
  return result as unknown as RunLogListResponse;
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
  downloadFile(result.download_url);
}

export async function getRunDepartments(): Promise<RunDepartmentInfo[]> {
  const result = await requestApi<RunDepartmentListResponse>("/runs/departments/");
  return result.departments;
}
