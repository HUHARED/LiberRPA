// FileName: serviceSettings.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse } from "./responses";

import type {
  ServiceSettingsRequest,
  ServiceSettingsResponse,
} from "./generated/browserApi";

function parseServiceSettingsResponse(payload: unknown): ServiceSettingsResponse {
  if (
    !isRecord(payload) ||
    typeof payload.allow_organization_creation !== "boolean" ||
    typeof payload.console_url !== "string" ||
    typeof payload.support_email !== "string"
  )
    return rejectInvalidResponse();

  return {
    allow_organization_creation: payload.allow_organization_creation,
    console_url: payload.console_url,
    support_email: payload.support_email,
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
