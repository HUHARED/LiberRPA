// FileName: apiKeys.ts

import { requestApi } from "./client";
import { isRecord, isDateString, rejectInvalidResponse } from "./responses";

import type {
  ApiKeyStatus,
  ApiKeyCreateRequest,
  ApiKeyCreationResponse,
  ApiKeyResponse,
  ApiKeyListResponse,
  ApiKeyNotesRequest,
  ApiKeyWriteResponse,
} from "./generated/browserApi";

function getApiKeyMetadata(apiKey: ApiKeyResponse): ApiKeyResponse {
  // Keep only metadata in tables and events; credentials belong only in the creation dialog.
  return {
    id: apiKey.id,
    name: apiKey.name,
    status: apiKey.status,
    expires_at: apiKey.expires_at,
    last_used_at: apiKey.last_used_at,
    notes: apiKey.notes,
    created_at: apiKey.created_at,
    revoked_at: apiKey.revoked_at,
  };
}

export function parseApiKeyCreationResponse(payload: unknown): ApiKeyCreationResponse {
  if (
    !isRecord(payload) ||
    typeof payload.secret !== "string" ||
    !payload.secret ||
    !isRecord(payload.api_key) ||
    typeof payload.api_key.id !== "string"
  )
    return rejectInvalidResponse();
  return {
    api_key: getApiKeyMetadata(payload.api_key as unknown as ApiKeyResponse),
    secret: payload.secret,
  };
}

function getApiKeyCollectionPath(memberId?: string): string {
  return memberId
    ? `/organization/members/${encodeURIComponent(memberId)}/api-keys/`
    : "/auth/api-keys/";
}

export async function getApiKeyList(
  statuses: ApiKeyStatus[],
  memberId?: string,
): Promise<ApiKeyListResponse> {
  const parameters = new URLSearchParams();
  for (const strStatus of statuses) parameters.append("status", strStatus);
  const response = await requestApi<ApiKeyListResponse>(
    `${getApiKeyCollectionPath(memberId)}?${parameters}`,
  );
  if (!isDateString(response.default_expires_at)) return rejectInvalidResponse();
  return {
    api_keys: response.api_keys.map(getApiKeyMetadata),
    default_expires_at: response.default_expires_at,
    limits: {
      active_keys: response.limits.active_keys,
      inactive_retention_days: response.limits.inactive_retention_days,
      inactive_records: response.limits.inactive_records,
    },
  };
}

export async function createApiKey(
  request: ApiKeyCreateRequest,
): Promise<ApiKeyCreationResponse> {
  return parseApiKeyCreationResponse(
    await requestApi("/auth/api-keys/", { method: "POST", body: request }),
  );
}

export async function updateApiKeyNotes(
  apiKeyId: string,
  notes: string,
): Promise<ApiKeyWriteResponse> {
  const request: ApiKeyNotesRequest = { notes };
  const response = await requestApi<ApiKeyWriteResponse>(
    `/auth/api-keys/${encodeURIComponent(apiKeyId)}/`,
    { method: "POST", body: request },
  );
  return { api_key: getApiKeyMetadata(response.api_key) };
}

export async function revokeApiKey(
  apiKeyId: string,
  memberId?: string,
): Promise<ApiKeyWriteResponse> {
  const response = await requestApi<ApiKeyWriteResponse>(
    `${getApiKeyCollectionPath(memberId)}${encodeURIComponent(apiKeyId)}/revoke/`,
    { method: "POST", body: {} },
  );
  return { api_key: getApiKeyMetadata(response.api_key) };
}

export function getApiKeyStatus(
  apiKey: ApiKeyResponse,
  currentTimeMs: number,
): ApiKeyStatus {
  return apiKey.status === "active" && Date.parse(apiKey.expires_at) <= currentTimeMs
    ? "expired"
    : apiKey.status;
}
