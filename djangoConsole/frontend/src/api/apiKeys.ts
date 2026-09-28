// FileName: apiKeys.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNonnegativeInteger,
  isDateString,
  isNullableDateString,
  rejectInvalidResponse,
} from "./responses";

import type {
  ApiKeyCreateRequest,
  ApiKeyCreationResponse,
  ApiKeyResponse,
  ApiKeyListResponse,
  ApiKeyNotesRequest,
  ApiKeyWriteResponse,
} from "./generated/browserApi";

export type ApiKeyStatus = ApiKeyResponse["status"];

function parseApiKey(payload: unknown): ApiKeyResponse {
  if (
    !isRecord(payload) ||
    typeof payload.id !== "string" ||
    typeof payload.name !== "string" ||
    (payload.status !== "active" &&
      payload.status !== "expired" &&
      payload.status !== "revoked") ||
    !isDateString(payload.expires_at) ||
    !isNullableDateString(payload.last_used_at) ||
    typeof payload.notes !== "string" ||
    !isDateString(payload.created_at) ||
    !isNullableDateString(payload.revoked_at)
  )
    return rejectInvalidResponse();
  // Keep only metadata in tables and events; credentials belong only in the creation dialog.
  return {
    id: payload.id,
    name: payload.name,
    status: payload.status,
    expires_at: payload.expires_at,
    last_used_at: payload.last_used_at,
    notes: payload.notes,
    created_at: payload.created_at,
    revoked_at: payload.revoked_at,
  };
}

export function parseApiKeyListResponse(payload: unknown): ApiKeyListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.api_keys) ||
    !isDateString(payload.default_expires_at) ||
    !isRecord(payload.limits) ||
    !isNonnegativeInteger(payload.limits.active_keys) ||
    !isNonnegativeInteger(payload.limits.inactive_retention_days) ||
    !isNonnegativeInteger(payload.limits.inactive_records)
  )
    return rejectInvalidResponse();
  return {
    api_keys: payload.api_keys.map(parseApiKey),
    default_expires_at: payload.default_expires_at,
    limits: {
      active_keys: payload.limits.active_keys,
      inactive_retention_days: payload.limits.inactive_retention_days,
      inactive_records: payload.limits.inactive_records,
    },
  };
}

export function parseApiKeyWriteResponse(payload: unknown): ApiKeyWriteResponse {
  if (!isRecord(payload)) return rejectInvalidResponse();
  return { api_key: parseApiKey(payload.api_key) };
}

export function parseApiKeyCreationResponse(payload: unknown): ApiKeyCreationResponse {
  if (!isRecord(payload) || typeof payload.secret !== "string" || !payload.secret)
    return rejectInvalidResponse();
  return { api_key: parseApiKey(payload.api_key), secret: payload.secret };
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
  for (const status of statuses) parameters.append("status", status);
  return parseApiKeyListResponse(
    await requestApi(`${getApiKeyCollectionPath(memberId)}?${parameters}`),
  );
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
  return parseApiKeyWriteResponse(
    await requestApi(`/auth/api-keys/${encodeURIComponent(apiKeyId)}/`, {
      method: "POST",
      body: request,
    }),
  );
}

export async function revokeApiKey(
  apiKeyId: string,
  memberId?: string,
): Promise<ApiKeyWriteResponse> {
  return parseApiKeyWriteResponse(
    await requestApi(
      `${getApiKeyCollectionPath(memberId)}${encodeURIComponent(apiKeyId)}/revoke/`,
      { method: "POST", body: {} },
    ),
  );
}

export function getApiKeyStatus(
  apiKey: ApiKeyResponse,
  currentTimeMs: number,
): ApiKeyStatus {
  return apiKey.status === "active" && Date.parse(apiKey.expires_at) <= currentTimeMs
    ? "expired"
    : apiKey.status;
}
