// FileName: audit.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNullableString,
  rejectInvalidResponse,
  parsePaginationResponse,
} from "./responses";

import {
  ARR_AUDIT_CHANNEL,
  ARR_AUDIT_RESULT_VALUE,
  ARR_AUDIT_STAGE,
  type AuditResult,
  type AuditDetailsResponse,
  type AuditChangeResponse,
  type AuditFilterOptionsResponse,
  type AuditActorResponse,
  type AuditListResponse,
  type AuditRecordResponse,
  type PlatformAuditRecordResponse,
  type PlatformAuditListResponse,
  type PlatformAuditFilterOptionsResponse,
  type PlatformAuditOrganizationResponse,
} from "./generated/browserApi";

export interface AuditListFilters {
  fromDate: string;
  toDate: string;
  timeZone: string;
  actorIds: string[];
  modules: string[];
  organizationIds: string[];
  actions: string[];
  results: AuditResult[];
}

function isAuditRecord(value: unknown): value is AuditRecordResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.created_at === "string" &&
    Number.isFinite(Date.parse(value.created_at)) &&
    isNullableString(value.actor_id) &&
    typeof value.actor_name === "string" &&
    ARR_AUDIT_CHANNEL.some((channel) => channel === value.channel) &&
    typeof value.module === "string" &&
    typeof value.action === "string" &&
    typeof value.object_type === "string" &&
    typeof value.object_id === "string" &&
    typeof value.object_name === "string" &&
    ARR_AUDIT_RESULT_VALUE.some((result) => result === value.result)
  );
}

export function parseAuditListResponse(
  payload: unknown,
  platform = false,
): AuditListResponse | PlatformAuditListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.records) ||
    !payload.records.every(isAuditRecord)
  )
    return rejectInvalidResponse();
  const pagination = parsePaginationResponse(payload.pagination);
  if (platform) {
    if (
      !payload.records.every(
        (record): record is PlatformAuditRecordResponse =>
          "organization_id" in record &&
          isNullableString(record.organization_id) &&
          "organization_name" in record &&
          typeof record.organization_name === "string",
      )
    )
      return rejectInvalidResponse();
    return { records: payload.records, pagination };
  }
  return { records: payload.records, pagination };
}

export function parseAuditFilterOptionsResponse(
  payload: unknown,
  platform = false,
): AuditFilterOptionsResponse | PlatformAuditFilterOptionsResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.actors) ||
    !payload.actors.every(
      (actor: unknown): actor is AuditActorResponse =>
        isRecord(actor) && isNullableString(actor.id) && typeof actor.name === "string",
    ) ||
    !Array.isArray(payload.actions) ||
    !payload.actions.every((action: unknown) => typeof action === "string")
  )
    return rejectInvalidResponse();
  if (platform) {
    if (
      !Array.isArray(payload.organizations) ||
      !payload.organizations.every(
        (organization: unknown): organization is PlatformAuditOrganizationResponse =>
          isRecord(organization) &&
          isNullableString(organization.id) &&
          typeof organization.name === "string",
      )
    )
      return rejectInvalidResponse();
    return {
      actors: payload.actors,
      organizations: payload.organizations,
      actions: payload.actions,
    };
  }
  if (
    !Array.isArray(payload.modules) ||
    !payload.modules.every((module: unknown) => typeof module === "string")
  )
    return rejectInvalidResponse();
  return { actors: payload.actors, modules: payload.modules, actions: payload.actions };
}

export function parseAuditDetailsResponse(payload: unknown): AuditDetailsResponse {
  if (!isRecord(payload) || !isRecord(payload.record) || !isAuditRecord(payload.record))
    return rejectInvalidResponse();
  const record = payload.record;
  const strStage = ARR_AUDIT_STAGE.find((stage) => stage === record.stage);
  if (
    !isNullableString(record.organization_id) ||
    typeof record.organization_name !== "string" ||
    !isNullableString(record.department_id) ||
    !isNullableString(record.request_id) ||
    strStage === undefined ||
    !isNullableString(record.reason) ||
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
      stage: strStage,
      reason: record.reason,
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
  platform = false,
): Promise<AuditListResponse | PlatformAuditListResponse> {
  const parameters = new URLSearchParams({
    page: String(pageNumber),
    time_zone: filters.timeZone,
  });
  if (filters.fromDate) parameters.set("date_from", filters.fromDate);
  if (filters.toDate) parameters.set("date_to", filters.toDate);
  for (const strActorId of filters.actorIds) parameters.append("actor_id", strActorId);
  if (platform) {
    for (const strOrganizationId of filters.organizationIds)
      parameters.append("organization_id", strOrganizationId);
  } else {
    for (const strModule of filters.modules) parameters.append("module", strModule);
  }
  for (const strAction of filters.actions) parameters.append("action", strAction);
  for (const strResult of filters.results) parameters.append("result", strResult);
  return parseAuditListResponse(
    await requestApi(`/${platform ? "platform" : "organization"}/audit/?${parameters}`),
    platform,
  );
}

export async function getAuditFilterOptions(
  platform = false,
  organizationId?: string,
): Promise<AuditFilterOptionsResponse | PlatformAuditFilterOptionsResponse> {
  const strQuery =
    platform && organizationId
      ? `?${new URLSearchParams({ organization_id: organizationId })}`
      : "";
  return parseAuditFilterOptionsResponse(
    await requestApi(
      `/${platform ? "platform" : "organization"}/audit/filters/${strQuery}`,
    ),
    platform,
  );
}

export async function getAuditDetails(
  auditId: string,
  platform = false,
): Promise<AuditDetailsResponse> {
  return parseAuditDetailsResponse(
    await requestApi(
      `/${platform ? "platform" : "organization"}/audit/${encodeURIComponent(auditId)}/`,
    ),
  );
}
