// FileName: organization.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse } from "./responses";

import type {
  OrganizationSettingsRequest,
  OrganizationSettingsResponse,
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
