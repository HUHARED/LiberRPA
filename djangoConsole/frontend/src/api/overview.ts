// FileName: overview.ts

import { requestApi } from "./client";
import type { CurrentRunListResponse, RunStatisticsResponse } from "./generated/browserApi";

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

export async function getCurrentRuns(
  filters: OverviewFilters,
  page = 1,
): Promise<CurrentRunListResponse> {
  const query = buildOverviewQuery(filters);
  query.set("page", String(page));
  return requestApi<CurrentRunListResponse>(`/runs/current/?${query}`);
}

export async function getRunStatistics(
  filters: RunStatisticsFilters,
  executorPage = 1,
): Promise<RunStatisticsResponse> {
  const query = buildOverviewQuery(filters);
  query.set("date_from", filters.dateFrom);
  query.set("date_until", filters.dateUntil);
  query.set("executor_page", String(executorPage));
  return requestApi<RunStatisticsResponse>(`/runs/statistics/?${query}`);
}
