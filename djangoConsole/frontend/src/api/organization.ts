// FileName: organization.ts

import { requestApi } from "./client";
import { parseOrganizationAccessResponse } from "./account";
import {
  isRecord,
  isNonnegativeInteger,
  rejectInvalidResponse,
  parseMessageResponse,
} from "./responses";

import {
  type MessageResponse,
  type OrganizationDeletionRequest,
  type OrganizationDeletionResponse,
  type OrganizationLimitsResponse,
  type OrganizationRetentionRequest,
  type OrganizationSettingsRequest,
  type OrganizationSettingsResponse,
  ARR_ORGANIZATION_LIMIT,
  ARR_LIMIT_UNIT,
} from "./generated/browserApi";

export function parseOrganizationDeletionResponse(
  payload: unknown,
): OrganizationDeletionResponse {
  if (
    !isRecord(payload) ||
    typeof payload.is_org_admin !== "boolean" ||
    typeof payload.business_available !== "boolean" ||
    typeof payload.can_schedule_deletion !== "boolean" ||
    typeof payload.can_cancel_deletion !== "boolean" ||
    !isNonnegativeInteger(payload.deletion_delay_days) ||
    payload.deletion_delay_days < 1
  )
    return rejectInvalidResponse();

  return {
    organization: parseOrganizationAccessResponse(payload.organization),
    is_org_admin: payload.is_org_admin,
    business_available: payload.business_available,
    can_schedule_deletion: payload.can_schedule_deletion,
    can_cancel_deletion: payload.can_cancel_deletion,
    deletion_delay_days: payload.deletion_delay_days,
  };
}

export function parseOrganizationLimitsResponse(
  payload: unknown,
): OrganizationLimitsResponse {
  if (
    !isRecord(payload) ||
    !isRecord(payload.organization) ||
    typeof payload.organization.id !== "string" ||
    !Array.isArray(payload.limits) ||
    !payload.limits.every(
      (limit: unknown) =>
        isRecord(limit) &&
        ARR_ORGANIZATION_LIMIT.some((key) => key === limit.key) &&
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
    !isRecord(payload.retention) ||
    !isNonnegativeInteger(payload.retention.run_log_days) ||
    !isNonnegativeInteger(payload.retention.run_log_max_days)
  )
    return rejectInvalidResponse();

  return payload as unknown as OrganizationLimitsResponse;
}

export async function getOrganizationSettings(): Promise<OrganizationSettingsResponse> {
  return requestApi<OrganizationSettingsResponse>("/organization/settings/");
}

export async function updateOrganizationSettings(
  request: OrganizationSettingsRequest,
): Promise<OrganizationSettingsResponse> {
  return requestApi<OrganizationSettingsResponse>("/organization/settings/", {
    method: "POST",
    body: request,
  });
}

export async function getOrganizationDeletion(): Promise<OrganizationDeletionResponse> {
  return parseOrganizationDeletionResponse(await requestApi("/organization/deletion/"));
}

export async function scheduleOrganizationDeletion(
  request: OrganizationDeletionRequest,
): Promise<OrganizationDeletionResponse> {
  return parseOrganizationDeletionResponse(
    await requestApi("/organization/deletion/", { method: "POST", body: request }),
  );
}

export async function cancelOrganizationDeletion(): Promise<OrganizationDeletionResponse> {
  return parseOrganizationDeletionResponse(
    await requestApi("/organization/deletion/cancel/", { method: "POST", body: {} }),
  );
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
