// FileName: audit.ts

import { requestApi } from "./client";

import type {
  AuditAction,
  AuditResult,
  AuditDetailsResponse,
  AuditFilterOptionsResponse,
  AuditListResponse,
  PlatformAuditListResponse,
  PlatformAuditFilterOptionsResponse,
} from "./generated/browserApi";

export interface AuditListFilters {
  fromDate: string;
  toDate: string;
  timeZone: string;
  actorIds: string[];
  modules: string[];
  organizationIds: string[];
  actions: AuditAction[];
  results: AuditResult[];
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
  return requestApi<AuditListResponse | PlatformAuditListResponse>(
    `/${platform ? "platform" : "organization"}/audit/?${parameters}`,
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
  return requestApi<AuditFilterOptionsResponse | PlatformAuditFilterOptionsResponse>(
    `/${platform ? "platform" : "organization"}/audit/filters/${strQuery}`,
  );
}

export async function getAuditDetails(
  auditId: string,
  platform = false,
): Promise<AuditDetailsResponse> {
  return requestApi<AuditDetailsResponse>(
    `/${platform ? "platform" : "organization"}/audit/${encodeURIComponent(auditId)}/`,
  );
}
