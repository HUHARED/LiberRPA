// FileName: schedules.ts

import { requestApi } from "./client";
import { isRecord, parsePaginationResponse, rejectInvalidResponse } from "./responses";
import type {
  ScheduleCreationRequest,
  ScheduleResponse,
  ScheduleListEntryResponse,
  ScheduleListResponse,
  ScheduleDefaultsResponse,
  SchedulePreviewResponse,
} from "./generated/browserApi";
import { isRunSettings, type RunSettings } from "./runOptions";

export type ScheduleDraft = Omit<Required<ScheduleCreationRequest>, "settings"> & {
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
function parseScheduleListEntry(value: unknown): ScheduleListEntry {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.name !== "string" ||
    typeof value.cron !== "string" ||
    typeof value.project_version !== "string" ||
    !isRecord(value.department) ||
    !Array.isArray(value.executor_ids) ||
    !Array.isArray(value.executors) ||
    typeof value.can_manage !== "boolean"
  )
    return rejectInvalidResponse();
  return value as unknown as ScheduleListEntry;
}
function parseSchedule(value: unknown): ScheduleInfo {
  parseScheduleListEntry(value);
  if (
    !isRecord(value) ||
    !isRunSettings(value.settings) ||
    typeof value.python_environment_name !== "string" ||
    !Array.isArray(value.upcoming_triggers) ||
    !value.upcoming_triggers.every((time: unknown) => typeof time === "string")
  )
    return rejectInvalidResponse();
  return value as unknown as ScheduleInfo;
}
export async function getScheduleDefaults(): Promise<ScheduleDefaultsResponse> {
  const result = await requestApi("/schedules/defaults/");
  if (!isRecord(result) || typeof result.time_zone !== "string")
    return rejectInvalidResponse();
  return { time_zone: result.time_zone };
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
  const result = await requestApi(`/schedules/?${query}`);
  if (!isRecord(result) || !Array.isArray(result.schedules)) return rejectInvalidResponse();
  return {
    schedules: result.schedules.map(parseScheduleListEntry),
    ...parsePaginationResponse(result),
  };
}
export async function getSchedule(id: string): Promise<ScheduleInfo> {
  const result = await requestApi(`/schedules/${encodeURIComponent(id)}/`);
  if (!isRecord(result)) return rejectInvalidResponse();
  return parseSchedule(result.schedule);
}
export async function saveSchedule(
  id: string | null,
  draft: ScheduleDraft,
): Promise<ScheduleInfo> {
  const body = id
    ? Object.fromEntries(Object.entries(draft).filter(([key]) => key !== "department_id"))
    : draft;
  const result = await requestApi(`/schedules/${id ? `${encodeURIComponent(id)}/` : ""}`, {
    method: "POST",
    body,
  });
  if (!isRecord(result)) return rejectInvalidResponse();
  return parseSchedule(result.schedule);
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
  const result = await requestApi("/schedules/preview/", { method: "POST", body });
  if (
    !isRecord(result) ||
    typeof result.normalized_cron !== "string" ||
    !Array.isArray(result.upcoming_triggers)
  )
    return rejectInvalidResponse();
  return result as unknown as SchedulePreviewResponse;
}
