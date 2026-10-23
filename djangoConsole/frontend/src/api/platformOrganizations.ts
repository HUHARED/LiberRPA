// FileName: platformOrganizations.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  isNullableDateString,
  rejectInvalidResponse,
  parsePaginationResponse,
  parseMessageResponse,
} from "./responses";
import { parseOrganizationLimitsResponse } from "./organization";

import type {
  PlatformOrganizationStatus,
  MessageResponse,
  OrganizationLimitsRequest,
  OrganizationLimitsResponse,
  OrganizationServiceRequest,
  PlatformOrganizationDetailsResponse,
  PlatformOrganizationListResponse,
  PlatformOrganizationResponse,
  ServiceSettingsRequest,
  ServiceSettingsResponse,
} from "./generated/browserApi";

function parseServiceSettingsResponse(payload: unknown): ServiceSettingsResponse {
  if (!isRecord(payload) || typeof payload.allow_organization_creation !== "boolean")
    return rejectInvalidResponse();

  return {
    allow_organization_creation: payload.allow_organization_creation,
  };
}

function parsePlatformOrganizationResponse(payload: unknown): PlatformOrganizationResponse {
  if (
    !isRecord(payload) ||
    typeof payload.id !== "string" ||
    typeof payload.name !== "string" ||
    typeof payload.notes !== "string" ||
    !isDateString(payload.created_at) ||
    !isNullableDateString(payload.suspended_at) ||
    !isNullableDateString(payload.deletion_requested_at) ||
    !isNullableDateString(payload.deletion_started_at) ||
    !Array.isArray(payload.administrators)
  )
    return rejectInvalidResponse();

  const arrAdministrator = payload.administrators.map((administrator: unknown) => {
    if (
      !isRecord(administrator) ||
      typeof administrator.id !== "string" ||
      typeof administrator.name !== "string" ||
      typeof administrator.email !== "string"
    )
      return rejectInvalidResponse();
    return { id: administrator.id, name: administrator.name, email: administrator.email };
  });
  return {
    id: payload.id,
    name: payload.name,
    notes: payload.notes,
    created_at: payload.created_at,
    suspended_at: payload.suspended_at,
    deletion_requested_at: payload.deletion_requested_at,
    deletion_started_at: payload.deletion_started_at,
    administrators: arrAdministrator,
  };
}

export function parsePlatformOrganizationListResponse(
  payload: unknown,
): PlatformOrganizationListResponse {
  if (!isRecord(payload) || !Array.isArray(payload.organizations))
    return rejectInvalidResponse();
  return {
    organizations: payload.organizations.map(parsePlatformOrganizationResponse),
    pagination: parsePaginationResponse(payload.pagination),
  };
}

export function parsePlatformOrganizationDetailsResponse(
  payload: unknown,
): PlatformOrganizationDetailsResponse {
  const organization = parsePlatformOrganizationResponse(payload);
  if (
    !isRecord(payload) ||
    typeof payload.default_time_zone !== "string" ||
    !isNullableDateString(payload.deletion_due_at)
  )
    return rejectInvalidResponse();
  return {
    ...organization,
    default_time_zone: payload.default_time_zone,
    deletion_due_at: payload.deletion_due_at,
  };
}

export async function getServiceSettings(): Promise<ServiceSettingsResponse> {
  return parseServiceSettingsResponse(await requestApi("/platform/service-settings/"));
}

export async function updateServiceSettings(
  request: ServiceSettingsRequest,
): Promise<ServiceSettingsResponse> {
  return parseServiceSettingsResponse(
    await requestApi("/platform/service-settings/", { method: "POST", body: request }),
  );
}

export async function getPlatformOrganizationList(
  filters: { name: string; organizationId: string; statuses: PlatformOrganizationStatus[] },
  pageNumber = 1,
): Promise<PlatformOrganizationListResponse> {
  const parameters = new URLSearchParams({ page: String(pageNumber) });
  if (filters.name.trim()) parameters.set("name", filters.name.trim());
  if (filters.organizationId.trim())
    parameters.set("organization_id", filters.organizationId.trim());
  for (const strStatus of filters.statuses) parameters.append("status", strStatus);
  return parsePlatformOrganizationListResponse(
    await requestApi(`/platform/organizations/?${parameters}`),
  );
}

export async function getPlatformOrganizationDetails(
  organizationId: string,
): Promise<PlatformOrganizationDetailsResponse> {
  return parsePlatformOrganizationDetailsResponse(
    await requestApi(`/platform/organizations/${encodeURIComponent(organizationId)}/`),
  );
}

export async function updateOrganizationService(
  organizationId: string,
  request: OrganizationServiceRequest,
): Promise<PlatformOrganizationDetailsResponse> {
  return parsePlatformOrganizationDetailsResponse(
    await requestApi(
      `/platform/organizations/${encodeURIComponent(organizationId)}/service/`,
      {
        method: "POST",
        body: request,
      },
    ),
  );
}

export async function getPlatformOrganizationLimits(
  organizationId: string,
): Promise<OrganizationLimitsResponse> {
  return parseOrganizationLimitsResponse(
    await requestApi(
      `/platform/organizations/${encodeURIComponent(organizationId)}/limits/`,
    ),
  );
}

export async function updateOrganizationLimits(
  organizationId: string,
  request: OrganizationLimitsRequest,
): Promise<MessageResponse> {
  return parseMessageResponse(
    await requestApi(
      `/platform/organizations/${encodeURIComponent(organizationId)}/limits/`,
      {
        method: "POST",
        body: request,
      },
    ),
  );
}
