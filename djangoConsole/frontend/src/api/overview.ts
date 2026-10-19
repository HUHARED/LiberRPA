// FileName: overview.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNonnegativeInteger,
  isDateString,
  rejectInvalidResponse,
  parsePaginationResponse,
} from "./responses";
import {
  RunStatus,
  type CurrentRunResponse,
  type CurrentRunListResponse,
  type RunResultCountResponse,
  type DailyRunStatisticsResponse,
  type ExecutorRunStatisticsResponse,
  type RunStatisticsResponse,
} from "./generated/browserApi";

export interface OverviewFilters {
  departmentIds: string[];
  projectName: string;
}

export interface RunStatisticsFilters extends OverviewFilters {
  dateFrom: string;
  dateUntil: string;
}

function buildOverviewQuery(filters: OverviewFilters): URLSearchParams {
  const query = new URLSearchParams();
  for (const strDepartmentId of filters.departmentIds)
    query.append("department_id", strDepartmentId);
  if (filters.projectName.trim()) query.set("project_name", filters.projectName.trim());
  return query;
}

function isDuration(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isResultCount(value: unknown): value is RunResultCountResponse {
  return (
    isRecord(value) &&
    Object.values(RunStatus).some(
      (status) => status !== RunStatus.Running && status === value.status,
    ) &&
    isNonnegativeInteger(value.count)
  );
}

export async function getCurrentRuns(
  filters: OverviewFilters,
  page = 1,
): Promise<CurrentRunListResponse> {
  const query = buildOverviewQuery(filters);
  query.set("page", String(page));
  const result = await requestApi(`/runs/current/?${query}`);
  if (
    !isRecord(result) ||
    !isDateString(result.updated_at) ||
    !Array.isArray(result.runs) ||
    !result.runs.every(
      (run: unknown): run is CurrentRunResponse =>
        isRecord(run) &&
        typeof run.id === "string" &&
        typeof run.project_name === "string" &&
        typeof run.project_version === "string" &&
        typeof run.executor_id === "string" &&
        typeof run.executor_name === "string" &&
        isDateString(run.started_at),
    )
  )
    return rejectInvalidResponse();
  return {
    runs: result.runs,
    updated_at: result.updated_at,
    ...parsePaginationResponse(result),
  };
}

export async function getRunStatistics(
  filters: RunStatisticsFilters,
  executorPage = 1,
): Promise<RunStatisticsResponse> {
  const query = buildOverviewQuery(filters);
  query.set("date_from", filters.dateFrom);
  query.set("date_until", filters.dateUntil);
  query.set("executor_page", String(executorPage));
  const result = await requestApi(`/runs/statistics/?${query}`);
  if (
    !isRecord(result) ||
    !isDateString(result.date_from) ||
    !isDateString(result.date_until) ||
    typeof result.time_zone !== "string" ||
    !isDateString(result.updated_at) ||
    !isNonnegativeInteger(result.total_count) ||
    !isDuration(result.total_duration_seconds) ||
    !Array.isArray(result.results) ||
    !result.results.every(isResultCount) ||
    !Array.isArray(result.daily) ||
    !result.daily.every(
      (day: unknown): day is DailyRunStatisticsResponse =>
        isRecord(day) &&
        isDateString(day.date) &&
        Array.isArray(day.results) &&
        day.results.every(isResultCount),
    ) ||
    !isRecord(result.executors) ||
    !Array.isArray(result.executors.entries) ||
    !result.executors.entries.every(
      (executor: unknown): executor is ExecutorRunStatisticsResponse =>
        isRecord(executor) &&
        typeof executor.id === "string" &&
        typeof executor.name === "string" &&
        isNonnegativeInteger(executor.total_count) &&
        isDuration(executor.duration_seconds) &&
        Array.isArray(executor.results) &&
        executor.results.every(isResultCount),
    )
  )
    return rejectInvalidResponse();
  return {
    date_from: result.date_from,
    date_until: result.date_until,
    time_zone: result.time_zone,
    updated_at: result.updated_at,
    total_count: result.total_count,
    total_duration_seconds: result.total_duration_seconds,
    results: result.results,
    daily: result.daily,
    executors: {
      entries: result.executors.entries,
      ...parsePaginationResponse(result.executors),
    },
  };
}
