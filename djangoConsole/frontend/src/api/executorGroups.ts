// FileName: executorGroups.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNonnegativeInteger,
  rejectInvalidResponse,
  parsePaginationResponse,
} from "./responses";
import { isExecutorListEntry } from "./executors";

import type {
  ExecutorGroupCreationRequest,
  ExecutorGroupDeletionRequest,
  ExecutorGroupDeletionResponse,
  ExecutorGroupRecordResponse,
  ExecutorGroupDetailsResponse,
  ExecutorGroupListResponse,
  ExecutorGroupListEntryResponse,
  ExecutorGroupUpdateRequest,
  ExecutorGroupWriteResponse,
  ExecutorGroupWriteEntryResponse,
  ExecutorGroupWarningResponse,
} from "./generated/browserApi";

export interface ExecutorGroupListFilters {
  name: string;
  departmentIds: string[];
}

function isGroupRecord(value: unknown): value is ExecutorGroupRecordResponse {
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
    isRecord(value) &&
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
    isRecord(value) &&
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
    !payload.executor_groups.every(isGroupListEntry)
  )
    return rejectInvalidResponse();
  return {
    executor_groups: payload.executor_groups,
    ...parsePaginationResponse(payload),
  };
}

export function parseExecutorGroupDetailsResponse(
  payload: unknown,
): ExecutorGroupDetailsResponse {
  if (
    !isRecord(payload) ||
    !isRecord(payload.executor_group) ||
    !isGroupListEntry(payload.executor_group) ||
    !Array.isArray(payload.executor_group.members) ||
    !payload.executor_group.members.every(isExecutorListEntry) ||
    payload.executor_group.member_count !== payload.executor_group.members.length
  )
    return rejectInvalidResponse();
  return {
    executor_group: {
      ...payload.executor_group,
      members: payload.executor_group.members,
    },
  };
}

export function parseExecutorGroupDeletionResponse(
  payload: unknown,
): ExecutorGroupDeletionResponse {
  if (!isRecord(payload) || !isGroupRecord(payload.executor_group))
    return rejectInvalidResponse();
  return { executor_group: payload.executor_group };
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
  for (const strDepartmentId of filters.departmentIds)
    queryParameters.append("department_id", strDepartmentId);
  return parseExecutorGroupListResponse(
    await requestApi(`/executor-groups/?${queryParameters}`),
  );
}

export async function getExecutorGroupDetails(
  groupId: string,
): Promise<ExecutorGroupDetailsResponse> {
  return parseExecutorGroupDetailsResponse(
    await requestApi(`/executor-groups/${encodeURIComponent(groupId)}/`),
  );
}

export async function createExecutorGroup(
  groupRequest: ExecutorGroupCreationRequest,
): Promise<ExecutorGroupWriteResponse> {
  return parseExecutorGroupWriteResponse(
    await requestApi("/executor-groups/", { method: "POST", body: groupRequest }),
  );
}

export async function updateExecutorGroup(
  groupId: string,
  changes: ExecutorGroupUpdateRequest,
): Promise<ExecutorGroupWriteResponse> {
  return parseExecutorGroupWriteResponse(
    await requestApi(`/executor-groups/${encodeURIComponent(groupId)}/`, {
      method: "POST",
      body: changes,
    }),
  );
}

export async function deleteExecutorGroup(
  groupId: string,
): Promise<ExecutorGroupDeletionResponse> {
  const deletionRequest: ExecutorGroupDeletionRequest = {};
  return parseExecutorGroupDeletionResponse(
    await requestApi(`/executor-groups/${encodeURIComponent(groupId)}/deletion/`, {
      method: "POST",
      body: deletionRequest,
    }),
  );
}
