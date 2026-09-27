// FileName: dataQueues.ts

import { requestApi } from "./client";
import { ApiError, isRecord } from "./errors";
import type {
  QueueCreationRequest,
  QueueDetailsRequest,
  QueueDetailsResponse,
  QueueEntryResponse,
  QueueItemDetailsResponse,
  QueueItemResponse,
  QueueItemsResponse,
  QueueListResponse,
  QueueMutationResponse,
  JsonValueInput as JsonValue,
} from "./generated/browserApi";

const ROOT = "/data-queues/";
export const QUEUE_STATUSES = [
  { title: "All", value: "all" },
  { title: "Unclaimed", value: "unclaimed" },
  { title: "Claimed", value: "claimed" },
];
export const QUEUE_ORDERS = [
  { title: "Oldest First", value: "oldest_first" },
  { title: "Newest First", value: "newest_first" },
];

function invalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}
function isQueue(value: unknown): value is QueueEntryResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.path === "string" &&
    typeof value.notes === "string" &&
    isRecord(value.department) &&
    typeof value.department.id === "string" &&
    typeof value.department.path === "string" &&
    typeof value.can_manage === "boolean" &&
    typeof value.unclaimed_count === "number" &&
    typeof value.claimed_count === "number" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}
function isItem(value: unknown): value is QueueItemResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.sequence === "number" &&
    ["unclaimed", "claimed"].includes(String(value.status)) &&
    typeof value.data_summary === "string" &&
    typeof value.uploaded_by_id === "string" &&
    typeof value.uploaded_by_name === "string" &&
    typeof value.uploaded_at === "string" &&
    (value.last_claimed_by_id === null || typeof value.last_claimed_by_id === "string") &&
    typeof value.last_claimed_by_name === "string" &&
    (value.last_claimed_at === null || typeof value.last_claimed_at === "string")
  );
}
function isPage(value: Record<string, unknown>): boolean {
  return (
    [value.page, value.page_size, value.total_pages].every(
      (entry) => typeof entry === "number" && Number.isSafeInteger(entry) && entry > 0,
    ) &&
    typeof value.total_count === "number" &&
    Number.isSafeInteger(value.total_count) &&
    value.total_count >= 0
  );
}
function details(payload: unknown): QueueDetailsResponse {
  if (!isRecord(payload) || !isQueue(payload.queue)) return invalidResponse();
  return { queue: payload.queue };
}
export async function getQueues(
  name: string,
  departments: string[],
  page: number,
): Promise<QueueListResponse> {
  const query = new URLSearchParams({ name, page: String(page) });
  departments.forEach((id) => query.append("department_id", id));
  const result = await requestApi(`${ROOT}?${query}`);
  if (
    !isRecord(result) ||
    !isPage(result) ||
    !Array.isArray(result.queues) ||
    !result.queues.every(isQueue)
  )
    return invalidResponse();
  return result as unknown as QueueListResponse;
}
export async function saveQueue(
  body: QueueCreationRequest | QueueDetailsRequest,
  id?: string,
): Promise<QueueDetailsResponse> {
  return details(
    await requestApi(id ? `${ROOT}${encodeURIComponent(id)}/` : ROOT, {
      method: "POST",
      body,
    }),
  );
}
export async function getQueueItems(
  id: string,
  status: string,
  order: string,
  itemId: string,
  page: number,
): Promise<QueueItemsResponse> {
  const query = new URLSearchParams({ status, order, page: String(page) });
  if (itemId) query.set("item_id", itemId);
  const result = await requestApi(`${ROOT}${encodeURIComponent(id)}/items/?${query}`);
  if (
    !isRecord(result) ||
    !isPage(result) ||
    !isQueue(result.queue) ||
    !Array.isArray(result.items) ||
    !result.items.every(isItem)
  )
    return invalidResponse();
  return result as unknown as QueueItemsResponse;
}
export async function getQueueItem(
  queueId: string,
  itemId: string,
): Promise<QueueItemDetailsResponse> {
  const result = await requestApi(
    `${ROOT}${encodeURIComponent(queueId)}/items/${encodeURIComponent(itemId)}/`,
  );
  if (!isItem(result) || !("data" in result)) return invalidResponse();
  return result as QueueItemDetailsResponse;
}
export async function deleteQueue(id: string): Promise<void> {
  const result = await requestApi(`${ROOT}${encodeURIComponent(id)}/deletion/`, {
    method: "POST",
    body: {},
  });
  if (!isRecord(result) || typeof result.message !== "string") invalidResponse();
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
  const digest = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (value) => value.toString(16).padStart(2, "0"),
  ).join("");
  const key = `queue-request:${userId}:${queueId}:${action}:${digest}`;
  const requestId = sessionStorage.getItem(key) ?? crypto.randomUUID();
  sessionStorage.setItem(key, requestId);
  const requestBody = { ...body, request_id: requestId };
  if (new TextEncoder().encode(JSON.stringify(requestBody)).length > 2 * 1024 * 1024)
    throw new ApiError("The complete request exceeds 2 MiB. Reduce this batch.");
  const result = await requestApi(`${ROOT}${encodeURIComponent(queueId)}/${action}/`, {
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
    return invalidResponse();
  sessionStorage.removeItem(key);
  return result as unknown as QueueMutationResponse;
}
