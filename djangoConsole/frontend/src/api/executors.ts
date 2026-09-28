// FileName: executors.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNullableString,
  isNullableDateString,
  rejectInvalidResponse,
  parsePaginationResponse,
} from "./responses";

import type {
  ExecutorCreationRequest,
  ExecutorDeletionRequest,
  ExecutorDetailsResponse,
  ExecutorGroupReferenceResponse,
  ExecutorDispatchRequest,
  ExecutorListEntryResponse,
  ExecutorListResponse,
  ExecutorUnassociateRequest,
  ExecutorUpdateRequest,
  ExecutorUpdateResponse,
  ExecutorRecordResponse,
} from "./generated/browserApi";

export interface ExecutorListFilters {
  name: string;
  departmentIds: string[];
  dispatchStates: boolean[];
}

function isExecutorRecord(value: unknown): value is ExecutorRecordResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.department_id === "string" &&
    typeof value.notes === "string" &&
    typeof value.dispatch_enabled === "boolean" &&
    typeof value.created_at === "string" &&
    isNullableDateString(value.created_at) &&
    isNullableDateString(value.deleted_at)
  );
}

export function isExecutorListEntry(value: unknown): value is ExecutorListEntryResponse {
  return (
    isRecord(value) &&
    isExecutorRecord(value) &&
    isRecord(value.department) &&
    typeof value.department.id === "string" &&
    typeof value.department.name === "string" &&
    typeof value.department.path === "string" &&
    typeof value.can_manage === "boolean" &&
    (value.association_status === "unassociated" ||
      value.association_status === "online" ||
      value.association_status === "offline") &&
    isNullableString(value.session_id) &&
    (value.account === null ||
      (isRecord(value.account) &&
        typeof value.account.id === "string" &&
        typeof value.account.email === "string" &&
        typeof value.account.username === "string")) &&
    isNullableString(value.computer) &&
    isNullableString(value.version) &&
    isNullableDateString(value.last_seen_at)
  );
}

export function parseExecutorListResponse(payload: unknown): ExecutorListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.executors) ||
    !payload.executors.every(isExecutorListEntry)
  )
    return rejectInvalidResponse();
  return {
    executors: payload.executors,
    ...parsePaginationResponse(payload),
  };
}

export function parseExecutorDetailsResponse(payload: unknown): ExecutorDetailsResponse {
  if (
    !isRecord(payload) ||
    !isRecord(payload.executor) ||
    !isExecutorListEntry(payload.executor) ||
    !Array.isArray(payload.executor.executor_groups) ||
    !payload.executor.executor_groups.every(
      (group: unknown): group is ExecutorGroupReferenceResponse =>
        isRecord(group) && typeof group.id === "string" && typeof group.name === "string",
    )
  )
    return rejectInvalidResponse();
  return {
    executor: {
      ...payload.executor,
      executor_groups: payload.executor.executor_groups,
    },
  };
}

export function parseExecutorUpdateResponse(payload: unknown): ExecutorUpdateResponse {
  if (!isRecord(payload) || !isExecutorRecord(payload.executor))
    return rejectInvalidResponse();
  return { executor: payload.executor };
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

export async function getExecutorDetails(
  executorId: string,
): Promise<ExecutorDetailsResponse> {
  return parseExecutorDetailsResponse(
    await requestApi(`/executors/${encodeURIComponent(executorId)}/`),
  );
}

export async function createExecutor(
  executorRequest: ExecutorCreationRequest,
): Promise<ExecutorUpdateResponse> {
  return parseExecutorUpdateResponse(
    await requestApi("/executors/", { method: "POST", body: executorRequest }),
  );
}

export async function deleteExecutor(executorId: string): Promise<ExecutorUpdateResponse> {
  const deletionRequest: ExecutorDeletionRequest = {};
  return parseExecutorUpdateResponse(
    await requestApi(`/executors/${encodeURIComponent(executorId)}/deletion/`, {
      method: "POST",
      body: deletionRequest,
    }),
  );
}

export async function updateExecutor(
  executorId: string,
  changes: ExecutorUpdateRequest,
): Promise<ExecutorUpdateResponse> {
  return parseExecutorUpdateResponse(
    await requestApi(`/executors/${encodeURIComponent(executorId)}/`, {
      method: "POST",
      body: changes,
    }),
  );
}

export async function setExecutorDispatch(
  executorId: string,
  dispatchEnabled: boolean,
): Promise<ExecutorUpdateResponse> {
  const dispatchRequest: ExecutorDispatchRequest = { dispatch_enabled: dispatchEnabled };
  return parseExecutorUpdateResponse(
    await requestApi(`/executors/${encodeURIComponent(executorId)}/dispatch/`, {
      method: "POST",
      body: dispatchRequest,
    }),
  );
}

export async function unassociateExecutor(
  executorId: string,
  sessionId: string,
): Promise<ExecutorUpdateResponse> {
  const unassociateRequest: ExecutorUnassociateRequest = { session_id: sessionId };
  return parseExecutorUpdateResponse(
    await requestApi(`/executors/${encodeURIComponent(executorId)}/unassociate/`, {
      method: "POST",
      body: unassociateRequest,
    }),
  );
}
