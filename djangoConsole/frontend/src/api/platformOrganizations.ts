// FileName: platformOrganizations.ts

import { requestApi } from "./client";
import { isRecord, isNullableDateString, rejectInvalidResponse } from "./responses";
import { parseOrganizationLimitsResponse } from "./organization";

import type {
  PlatformOrganizationStatus,
  OrganizationLimitsRequest,
  OrganizationLimitsResponse,
  OrganizationServiceRequest,
  PlatformOrganizationDetailsResponse,
  PlatformOrganizationListResponse,
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

export function parsePlatformOrganizationDetailsResponse(
  payload: unknown,
): PlatformOrganizationDetailsResponse {
  if (
    !isRecord(payload) ||
    typeof payload.id !== "string" ||
    !isNullableDateString(payload.suspended_at) ||
    !isNullableDateString(payload.deletion_requested_at) ||
    !isNullableDateString(payload.deletion_started_at)
  )
    return rejectInvalidResponse();
  return payload as unknown as PlatformOrganizationDetailsResponse;
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
  return requestApi<PlatformOrganizationListResponse>(
    `/platform/organizations/?${parameters}`,
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
): Promise<void> {
  await requestApi(
    `/platform/organizations/${encodeURIComponent(organizationId)}/limits/`,
    {
      method: "POST",
      body: request,
    },
  );
}
