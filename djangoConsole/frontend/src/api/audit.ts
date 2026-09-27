// FileName: audit.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";
import { parsePaginationResponse } from "./members";

import type {
  AuditDetailsResponse,
  AuditChangeResponse,
  AuditFilterOptionsResponse,
  AuditActorResponse,
  AuditListResponse,
  AuditRecordResponse,
} from "./generated/browserApi";

export interface AuditListFilters {
  fromDate: string;
  toDate: string;
  timeZone: string;
  actorIds: string[];
  modules: string[];
  actions: string[];
  results: string[];
}

function rejectInvalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isAuditRecord(value: unknown): value is AuditRecordResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.created_at === "string" &&
    Number.isFinite(Date.parse(value.created_at)) &&
    isNullableString(value.actor_id) &&
    typeof value.actor_name === "string" &&
    typeof value.channel === "string" &&
    ["session", "executor", "api_key", "system"].includes(value.channel) &&
    typeof value.module === "string" &&
    typeof value.action === "string" &&
    typeof value.object_type === "string" &&
    typeof value.object_id === "string" &&
    typeof value.object_name === "string" &&
    (value.result === "succeeded" || value.result === "failed")
  );
}

export function parseAuditListResponse(payload: unknown): AuditListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.records) ||
    !payload.records.every(isAuditRecord)
  )
    return rejectInvalidResponse();
  return {
    records: payload.records,
    pagination: parsePaginationResponse(payload.pagination),
  };
}

export function parseAuditFilterOptionsResponse(
  payload: unknown,
): AuditFilterOptionsResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.actors) ||
    !payload.actors.every(
      (actor: unknown): actor is AuditActorResponse =>
        isRecord(actor) && isNullableString(actor.id) && typeof actor.name === "string",
    ) ||
    !Array.isArray(payload.modules) ||
    !payload.modules.every((module: unknown) => typeof module === "string") ||
    !Array.isArray(payload.actions) ||
    !payload.actions.every((action: unknown) => typeof action === "string")
  )
    return rejectInvalidResponse();
  return { actors: payload.actors, modules: payload.modules, actions: payload.actions };
}

export function parseAuditDetailsResponse(payload: unknown): AuditDetailsResponse {
  if (!isRecord(payload) || !isRecord(payload.record) || !isAuditRecord(payload.record))
    return rejectInvalidResponse();
  const record = payload.record;
  if (
    typeof record.organization_id !== "string" ||
    typeof record.organization_name !== "string" ||
    !isNullableString(record.department_id) ||
    !isNullableString(record.request_id) ||
    (record.stage !== "operation" && record.stage !== "request") ||
    !isNullableString(record.reason_code) ||
    !(
      record.http_status === null ||
      (typeof record.http_status === "number" && Number.isInteger(record.http_status))
    ) ||
    !Array.isArray(record.changes) ||
    !record.changes.every(
      (change: unknown): change is AuditChangeResponse =>
        isRecord(change) &&
        typeof change.field === "string" &&
        isNullableString(change.before) &&
        isNullableString(change.after),
    ) ||
    typeof record.details_omitted !== "boolean"
  )
    return rejectInvalidResponse();
  return {
    record: {
      ...record,
      organization_id: record.organization_id,
      organization_name: record.organization_name,
      department_id: record.department_id,
      request_id: record.request_id,
      stage: record.stage,
      reason_code: record.reason_code,
      http_status: record.http_status,
      changes: record.changes,
      details_omitted: record.details_omitted,
    },
  };
}

export async function getAuditList(
  filters: AuditListFilters,
  pageNumber: number,
): Promise<AuditListResponse> {
  const parameters = new URLSearchParams({
    page: String(pageNumber),
    time_zone: filters.timeZone,
  });
  if (filters.fromDate) parameters.set("date_from", filters.fromDate);
  if (filters.toDate) parameters.set("date_to", filters.toDate);
  for (const actorId of filters.actorIds) parameters.append("actor_id", actorId);
  for (const module of filters.modules) parameters.append("module", module);
  for (const action of filters.actions) parameters.append("action", action);
  for (const result of filters.results) parameters.append("result", result);
  return parseAuditListResponse(await requestApi(`/organization/audit/?${parameters}`));
}

export async function getAuditFilterOptions(): Promise<AuditFilterOptionsResponse> {
  return parseAuditFilterOptionsResponse(await requestApi("/organization/audit/filters/"));
}

export async function getAuditDetails(auditId: string): Promise<AuditDetailsResponse> {
  return parseAuditDetailsResponse(
    await requestApi(`/organization/audit/${encodeURIComponent(auditId)}/`),
  );
}
