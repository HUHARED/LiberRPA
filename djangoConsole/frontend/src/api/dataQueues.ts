// FileName: dataQueues.ts

import { requestApi } from "./client";
import { ApiError } from "./errors";
import { isRecord, rejectInvalidResponse, parseMessageResponse } from "./responses";

import type {
  QueueItemFilterStatus,
  QueueItemOrder,
  QueueCreationRequest,
  QueueDetailsRequest,
  QueueDetailsResponse,
  QueueItemDetailsResponse,
  QueueItemsResponse,
  QueueListResponse,
  QueueMutationResponse,
  JsonValue,
} from "./generated/browserApi";

const API_ROOT = "/data-queues/";

export async function getQueues(
  name: string,
  departmentIds: string[],
  page: number,
): Promise<QueueListResponse> {
  const query = new URLSearchParams({ name, page: String(page) });
  departmentIds.forEach((id) => query.append("department_id", id));
  return requestApi<QueueListResponse>(`${API_ROOT}?${query}`);
}
export async function saveQueue(
  body: QueueCreationRequest | QueueDetailsRequest,
  queueId?: string,
): Promise<QueueDetailsResponse> {
  return requestApi<QueueDetailsResponse>(
    queueId ? `${API_ROOT}${encodeURIComponent(queueId)}/` : API_ROOT,
    { method: "POST", body },
  );
}
export async function getQueueItems(
  queueId: string,
  status: QueueItemFilterStatus,
  order: QueueItemOrder,
  itemId: string,
  page: number,
): Promise<QueueItemsResponse> {
  const query = new URLSearchParams({ status, order, page: String(page) });
  if (itemId) query.set("item_id", itemId);
  return requestApi<QueueItemsResponse>(
    `${API_ROOT}${encodeURIComponent(queueId)}/items/?${query}`,
  );
}
export async function getQueueItem(
  queueId: string,
  itemId: string,
): Promise<QueueItemDetailsResponse> {
  return requestApi<QueueItemDetailsResponse>(
    `${API_ROOT}${encodeURIComponent(queueId)}/items/${encodeURIComponent(itemId)}/`,
  );
}
export async function deleteQueue(queueId: string): Promise<void> {
  const result = await requestApi(`${API_ROOT}${encodeURIComponent(queueId)}/deletion/`, {
    method: "POST",
    body: {},
  });
  parseMessageResponse(result);
}
export async function changeQueueItems(
  userId: string,
  queueId: string,
  action: "upload" | "reset" | "delete_items",
  body: { items: JsonValue[] } | { item_ids: string[] },
): Promise<QueueMutationResponse> {
  // Persist only the request identity and a digest, so reloads can retry without storing business JSON.
  const bytes = new TextEncoder().encode(
    JSON.stringify(body, (_key: string, value: unknown) =>
      isRecord(value)
        ? Object.fromEntries(
            Object.keys(value)
              .sort()
              .map((key) => [key, value[key]]),
          )
        : value,
    ),
  );
  const strDigest = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (value) => value.toString(16).padStart(2, "0"),
  ).join("");
  const strKey = `queue-request:${userId}:${queueId}:${action}:${strDigest}`;
  const strRequestId = sessionStorage.getItem(strKey) ?? crypto.randomUUID();
  sessionStorage.setItem(strKey, strRequestId);
  const requestBody = { ...body, request_id: strRequestId };
  if (new TextEncoder().encode(JSON.stringify(requestBody)).length > 2 * 1024 * 1024)
    throw new ApiError("The complete request exceeds 2 MiB. Reduce this batch.");
  const result = await requestApi(`${API_ROOT}${encodeURIComponent(queueId)}/${action}/`, {
    method: "POST",
    body: requestBody,
  });
  if (
    !isRecord(result) ||
    typeof result.request_id !== "string" ||
    typeof result.accepted_at !== "string" ||
    typeof result.deduplicated !== "boolean" ||
    ![result.item_ids, result.missing_ids, result.skipped_ids].every(
      (ids) => Array.isArray(ids) && ids.every((id) => typeof id === "string"),
    ) ||
    !Array.isArray(result.items)
  )
    return rejectInvalidResponse();
  sessionStorage.removeItem(strKey);
  return result as unknown as QueueMutationResponse;
}
