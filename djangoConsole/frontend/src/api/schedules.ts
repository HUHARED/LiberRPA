// FileName: schedules.ts

import { requestApi } from "./client";
import type {
  ScheduleSaveRequest,
  ScheduleListEntryResponse,
  ScheduleResponse,
  ScheduleListResponse,
  ScheduleDetailsResponse,
  SchedulePreviewResponse,
} from "./generated/browserApi";
import type { RunSettings } from "./runSettings";

export type ScheduleDraft = Omit<Required<ScheduleSaveRequest>, "settings"> & {
  settings: RunSettings;
};
export type ScheduleInfo = ScheduleResponse;
export type ScheduleListEntry = ScheduleListEntryResponse;
export type SchedulePage = ScheduleListResponse;

export interface ScheduleFilters {
  name: string;
  departmentIds: string[];
  projectName: string;
  enabled: "" | "true" | "false";
  targetId: string | null;
}

export async function getSchedules(
  filters: ScheduleFilters,
  page = 1,
): Promise<SchedulePage> {
  const query = new URLSearchParams({
    page: String(page),
    name: filters.name,
    project_name: filters.projectName,
    target: filters.targetId ?? "",
  });
  if (filters.enabled) query.set("enabled", filters.enabled);
  for (const id of filters.departmentIds) query.append("department_id", id);
  return requestApi<ScheduleListResponse>(`/schedules/?${query}`);
}

export async function getSchedule(id: string): Promise<ScheduleInfo> {
  const result = await requestApi<ScheduleDetailsResponse>(
    `/schedules/${encodeURIComponent(id)}/`,
  );
  return result.schedule;
}

export async function saveSchedule(
  id: string | null,
  draft: ScheduleDraft,
): Promise<ScheduleInfo> {
  const result = await requestApi<ScheduleDetailsResponse>(
    `/schedules/${id ? `${encodeURIComponent(id)}/` : ""}`,
    {
      method: "POST",
      body: draft,
    },
  );
  return result.schedule;
}

export async function setScheduleEnabled(id: string, enabled: boolean): Promise<void> {
  await requestApi(`/schedules/${encodeURIComponent(id)}/enabled/`, {
    method: "POST",
    body: { enabled },
  });
}

export async function deleteSchedule(id: string): Promise<void> {
  await requestApi(`/schedules/${encodeURIComponent(id)}/delete/`, {
    method: "POST",
    body: {},
  });
}

export async function previewSchedule(
  body: Pick<ScheduleDraft, "cron" | "time_zone" | "active_from" | "active_until">,
): Promise<SchedulePreviewResponse> {
  return requestApi<SchedulePreviewResponse>("/schedules/preview/", {
    method: "POST",
    body,
  });
}
