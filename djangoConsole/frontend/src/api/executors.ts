// FileName: executors.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";

import type {
  ExecutorListResponse,
  ExecutorListEntryResponse,
} from "./generated/browserApi";

export interface ExecutorListFilters {
  name: string;
  departmentIds: string[];
  dispatchStates: boolean[];
}

function isNullableText(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableDate(value: unknown): value is string | null {
  return (
    value === null || (typeof value === "string" && Number.isFinite(Date.parse(value)))
  );
}

function isExecutorListEntry(value: unknown): value is ExecutorListEntryResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.department_id === "string" &&
    typeof value.notes === "string" &&
    typeof value.dispatch_enabled === "boolean" &&
    typeof value.created_at === "string" &&
    isNullableDate(value.created_at) &&
    isNullableDate(value.deleted_at) &&
    isRecord(value.department) &&
    typeof value.department.id === "string" &&
    typeof value.department.name === "string" &&
    typeof value.department.path === "string" &&
    typeof value.can_manage === "boolean" &&
    (value.association_status === "unassociated" ||
      value.association_status === "online" ||
      value.association_status === "offline") &&
    isNullableText(value.session_id) &&
    (value.account === null ||
      (isRecord(value.account) &&
        typeof value.account.id === "string" &&
        typeof value.account.email === "string" &&
        typeof value.account.username === "string")) &&
    isNullableText(value.computer) &&
    isNullableText(value.version) &&
    isNullableDate(value.last_seen_at)
  );
}

export function parseExecutorListResponse(payload: unknown): ExecutorListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.executors) ||
    !payload.executors.every(isExecutorListEntry) ||
    typeof payload.page !== "number" ||
    !Number.isSafeInteger(payload.page) ||
    payload.page < 1 ||
    typeof payload.page_size !== "number" ||
    !Number.isSafeInteger(payload.page_size) ||
    payload.page_size < 1 ||
    typeof payload.total_count !== "number" ||
    !Number.isSafeInteger(payload.total_count) ||
    payload.total_count < 0 ||
    typeof payload.total_pages !== "number" ||
    !Number.isSafeInteger(payload.total_pages) ||
    payload.total_pages < 1
  ) {
    throw new ApiError("The service returned an unexpected response. Please try again.", {
      code: "invalid_response",
    });
  }
  return {
    executors: payload.executors,
    page: payload.page,
    page_size: payload.page_size,
    total_count: payload.total_count,
    total_pages: payload.total_pages,
  };
}

export async function getExecutorList(
  filters: ExecutorListFilters,
  pageNumber: number,
): Promise<ExecutorListResponse> {
  const queryParameters = new URLSearchParams({ page: String(pageNumber) });
  if (filters.name) queryParameters.set("name", filters.name);
  for (const departmentId of filters.departmentIds)
    queryParameters.append("department_id", departmentId);
  for (const dispatchEnabled of filters.dispatchStates)
    queryParameters.append("dispatch_enabled", String(dispatchEnabled));
  return parseExecutorListResponse(await requestApi(`/executors/?${queryParameters}`));
}
