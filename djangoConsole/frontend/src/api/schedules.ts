// FileName: schedules.ts

import { requestApi } from "./client";
import { isRecord, parsePaginationResponse, rejectInvalidResponse } from "./responses";
import type { PaginationResponse } from "./generated/browserApi";
import type { RunSettings } from "./runOptions";

export interface ScheduleDraft {
  name: string;
  department_id: string;
  package_id: string;
  executor_ids: string[];
  group_id: string | null;
  enabled: boolean;
  notes: string;
  cron: string;
  time_zone: string;
  active_from: string;
  active_until: string;
  settings: RunSettings;
}
export interface ScheduleInfo extends ScheduleDraft {
  id: string;
  department: { id: string; name: string; path: string };
  project_name: string;
  project_version: string;
  created_by: { id: string; username: string; email: string } | null;
  can_manage: boolean;
  upcoming_triggers: string[];
  python_environment_name?: string;
  executors?: { id: string; name: string }[];
  executor_group?: { id: string; name: string } | null;
}
export interface SchedulePage extends PaginationResponse {
  schedules: ScheduleInfo[];
}
export interface ScheduleFilters {
  name: string;
  departmentIds: string[];
  project: string;
  enabled: string;
  target: string;
}
function parseSchedule(value: unknown): ScheduleInfo {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.name !== "string" ||
    typeof value.cron !== "string" ||
    !isRecord(value.department)
  )
    return rejectInvalidResponse();
  return value as unknown as ScheduleInfo;
}
export async function getSchedules(
  filters: ScheduleFilters,
  page = 1,
): Promise<SchedulePage> {
  const query = new URLSearchParams({
    page: String(page),
    name: filters.name,
    project_name: filters.project,
    target: filters.target ?? "",
  });
  if (filters.enabled) query.set("enabled", filters.enabled);
  for (const id of filters.departmentIds) query.append("department_id", id);
  const result = await requestApi(`/schedules/?${query}`);
  if (!isRecord(result) || !Array.isArray(result.schedules)) return rejectInvalidResponse();
  return {
    schedules: result.schedules.map(parseSchedule),
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
): Promise<{ normalized_cron: string; upcoming_triggers: string[] }> {
  const result = await requestApi("/schedules/preview/", { method: "POST", body });
  if (
    !isRecord(result) ||
    typeof result.normalized_cron !== "string" ||
    !Array.isArray(result.upcoming_triggers)
  )
    return rejectInvalidResponse();
  return result as unknown as { normalized_cron: string; upcoming_triggers: string[] };
}
export function formatScheduleDateInput(value: string, timeZone: string): string {
  const mapPart = new Map(
    new Intl.DateTimeFormat("en", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(new Date(value))
      .map((part) => [part.type, part.value]),
  );
  return `${mapPart.get("year")}-${mapPart.get("month")}-${mapPart.get("day")}T${mapPart.get("hour")}:${mapPart.get("minute")}:${mapPart.get("second")}`;
}
