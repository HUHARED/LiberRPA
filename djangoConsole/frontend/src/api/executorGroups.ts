// FileName: executorGroups.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";

import type {
  ExecutorGroupCreationRequest,
  ExecutorGroupListResponse,
  ExecutorGroupListEntryResponse,
  ExecutorGroupWriteResponse,
  ExecutorGroupWriteEntryResponse,
  ExecutorGroupWarningResponse,
} from "./generated/browserApi";

export interface ExecutorGroupListFilters {
  name: string;
  departmentIds: string[];
}

function rejectInvalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isGroupRecord(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.department_id === "string" &&
    typeof value.notes === "string" &&
    typeof value.created_at === "string" &&
    Number.isFinite(Date.parse(value.created_at)) &&
    (value.deleted_at === null ||
      (typeof value.deleted_at === "string" &&
        Number.isFinite(Date.parse(value.deleted_at))))
  );
}

function isGroupListEntry(value: unknown): value is ExecutorGroupListEntryResponse {
  return (
    isGroupRecord(value) &&
    isRecord(value.department) &&
    typeof value.department.id === "string" &&
    typeof value.department.name === "string" &&
    typeof value.department.path === "string" &&
    typeof value.can_manage === "boolean" &&
    isNonnegativeInteger(value.member_count) &&
    isNonnegativeInteger(value.online_count) &&
    value.online_count <= value.member_count &&
    value.is_empty === (value.member_count === 0)
  );
}

function isGroupWriteEntry(value: unknown): value is ExecutorGroupWriteEntryResponse {
  return (
    isGroupRecord(value) &&
    Array.isArray(value.executor_ids) &&
    value.executor_ids.every((executorId: unknown) => typeof executorId === "string") &&
    isNonnegativeInteger(value.member_count) &&
    value.member_count === value.executor_ids.length &&
    value.is_empty === (value.member_count === 0)
  );
}

export function parseExecutorGroupListResponse(
  payload: unknown,
): ExecutorGroupListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.executor_groups) ||
    !payload.executor_groups.every(isGroupListEntry) ||
    !isNonnegativeInteger(payload.page) ||
    payload.page < 1 ||
    !isNonnegativeInteger(payload.page_size) ||
    payload.page_size < 1 ||
    !isNonnegativeInteger(payload.total_count) ||
    !isNonnegativeInteger(payload.total_pages) ||
    payload.total_pages < 1
  )
    return rejectInvalidResponse();
  return {
    executor_groups: payload.executor_groups,
    page: payload.page,
    page_size: payload.page_size,
    total_count: payload.total_count,
    total_pages: payload.total_pages,
  };
}

export function parseExecutorGroupWriteResponse(
  payload: unknown,
): ExecutorGroupWriteResponse {
  if (
    !isRecord(payload) ||
    !isGroupWriteEntry(payload.executor_group) ||
    !Array.isArray(payload.warnings) ||
    !payload.warnings.every(
      (warning: unknown): warning is ExecutorGroupWarningResponse =>
        isRecord(warning) &&
        warning.code === "empty_executor_group" &&
        typeof warning.message === "string",
    )
  )
    return rejectInvalidResponse();
  return { executor_group: payload.executor_group, warnings: payload.warnings };
}

export async function getExecutorGroupList(
  filters: ExecutorGroupListFilters,
  pageNumber: number,
): Promise<ExecutorGroupListResponse> {
  const queryParameters = new URLSearchParams({ page: String(pageNumber) });
  if (filters.name) queryParameters.set("name", filters.name);
  for (const departmentId of filters.departmentIds)
    queryParameters.append("department_id", departmentId);
  return parseExecutorGroupListResponse(
    await requestApi(`/executor-groups/?${queryParameters}`),
  );
}

export async function createExecutorGroup(
  groupRequest: ExecutorGroupCreationRequest,
): Promise<ExecutorGroupWriteResponse> {
  return parseExecutorGroupWriteResponse(
    await requestApi("/executor-groups/", { method: "POST", body: groupRequest }),
  );
}
