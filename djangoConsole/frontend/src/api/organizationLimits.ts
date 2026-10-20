// FileName: organizationLimits.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  isNullableDateString,
  isNonnegativeInteger,
  parsePaginationResponse,
  parseMessageResponse,
  isNullableString,
  rejectInvalidResponse,
} from "./responses";

import {
  ARR_ORGANIZATION_LIMIT,
  ARR_LIMIT_UNIT,
  type OrganizationLimitResponse,
  type MessageResponse,
  type OrganizationLimitsRequest,
  type OrganizationLimitsResponse,
  type OrganizationRetentionRequest,
  type PlatformOrganizationResponse,
  type PlatformOrganizationListResponse,
  type PlatformOrganizationDetailsResponse,
  type OrganizationServiceRequest,
  type PlatformOrganizationStatus,
} from "./generated/browserApi";

export function parseOrganizationLimitsResponse(
  payload: unknown,
): OrganizationLimitsResponse {
  if (
    !isRecord(payload) ||
    !isRecord(payload.organization) ||
    typeof payload.organization.id !== "string" ||
    typeof payload.organization.name !== "string" ||
    !Array.isArray(payload.limits) ||
    !payload.limits.every(
      (limit: unknown): limit is OrganizationLimitResponse =>
        isRecord(limit) &&
        ARR_ORGANIZATION_LIMIT.some((key) => key === limit.key) &&
        typeof limit.label === "string" &&
        ARR_LIMIT_UNIT.some((unit) => unit === limit.unit) &&
        (limit.used === null || isNonnegativeInteger(limit.used)) &&
        (limit.reserved === null || isNonnegativeInteger(limit.reserved)) &&
        isNonnegativeInteger(limit.limit) &&
        isNonnegativeInteger(limit.default_limit) &&
        (limit.override === null || isNonnegativeInteger(limit.override)) &&
        isNonnegativeInteger(limit.minimum) &&
        (limit.maximum === null || isNonnegativeInteger(limit.maximum)),
    ) ||
    typeof payload.version !== "string" ||
    !isDateString(payload.updated_at) ||
    !isNullableString(payload.usage_warning) ||
    !isRecord(payload.retention) ||
    !isNonnegativeInteger(payload.retention.run_log_days) ||
    !isNonnegativeInteger(payload.retention.run_log_max_days) ||
    !isNonnegativeInteger(payload.retention.run_history_days) ||
    !isNonnegativeInteger(payload.retention.audit_days)
  )
    return rejectInvalidResponse();

  return {
    organization: { id: payload.organization.id, name: payload.organization.name },
    limits: payload.limits,
    version: payload.version,
    updated_at: payload.updated_at,
    usage_warning: payload.usage_warning,
    retention: {
      run_log_days: payload.retention.run_log_days,
      run_log_max_days: payload.retention.run_log_max_days,
      run_history_days: payload.retention.run_history_days,
      audit_days: payload.retention.audit_days,
    },
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

export async function getOrganizationUsage(): Promise<OrganizationLimitsResponse> {
  return parseOrganizationLimitsResponse(await requestApi("/organization/usage/"));
}

export async function updateOrganizationRetention(
  request: OrganizationRetentionRequest,
): Promise<MessageResponse> {
  return parseMessageResponse(
    await requestApi("/organization/retention/", { method: "POST", body: request }),
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
