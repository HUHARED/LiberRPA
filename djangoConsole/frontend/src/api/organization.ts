// FileName: organization.ts

import { requestApi } from "./client";
import { parseOrganizationAccessResponse } from "./account";
import {
  isRecord,
  isNonnegativeInteger,
  isNullableString,
  isDateString,
  rejectInvalidResponse,
  parseMessageResponse,
} from "./responses";

import {
  type MessageResponse,
  type OrganizationDeletionRequest,
  type OrganizationDeletionResponse,
  type OrganizationLimitsResponse,
  type OrganizationLimitResponse,
  type OrganizationRetentionRequest,
  type OrganizationSettingsRequest,
  type OrganizationSettingsResponse,
  ARR_ORGANIZATION_LIMIT,
  ARR_LIMIT_UNIT,
} from "./generated/browserApi";

export function parseOrganizationSettingsResponse(
  payload: unknown,
): OrganizationSettingsResponse {
  if (
    !isRecord(payload) ||
    !isRecord(payload.organization) ||
    typeof payload.organization.id !== "string" ||
    typeof payload.organization.name !== "string" ||
    typeof payload.organization.default_time_zone !== "string" ||
    !payload.organization.default_time_zone ||
    typeof payload.organization.notes !== "string"
  )
    return rejectInvalidResponse();
  return {
    organization: {
      id: payload.organization.id,
      name: payload.organization.name,
      default_time_zone: payload.organization.default_time_zone,
      notes: payload.organization.notes,
    },
  };
}

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

export async function getOrganizationSettings(): Promise<OrganizationSettingsResponse> {
  return parseOrganizationSettingsResponse(await requestApi("/organization/settings/"));
}

export async function updateOrganizationSettings(
  request: OrganizationSettingsRequest,
): Promise<OrganizationSettingsResponse> {
  return parseOrganizationSettingsResponse(
    await requestApi("/organization/settings/", { method: "POST", body: request }),
  );
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
