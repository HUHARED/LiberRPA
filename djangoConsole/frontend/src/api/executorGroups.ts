// FileName: executorGroups.ts

import { requestApi } from "./client";

import type {
  ExecutorGroupCreationRequest,
  ExecutorGroupDeletionRequest,
  ExecutorGroupDeletionResponse,
  ExecutorGroupDetailsResponse,
  ExecutorGroupListResponse,
  ExecutorGroupUpdateRequest,
  ExecutorGroupWriteResponse,
} from "./generated/browserApi";

export interface ExecutorGroupListFilters {
  name: string;
  departmentIds: string[];
}

export async function getExecutorGroupList(
  filters: ExecutorGroupListFilters,
  pageNumber: number,
): Promise<ExecutorGroupListResponse> {
  const queryParameters = new URLSearchParams({ page: String(pageNumber) });
  if (filters.name) queryParameters.set("name", filters.name);
  for (const strDepartmentId of filters.departmentIds)
    queryParameters.append("department_id", strDepartmentId);
  return requestApi<ExecutorGroupListResponse>(`/executor-groups/?${queryParameters}`);
}

export async function getExecutorGroupDetails(
  groupId: string,
): Promise<ExecutorGroupDetailsResponse> {
  return requestApi<ExecutorGroupDetailsResponse>(
    `/executor-groups/${encodeURIComponent(groupId)}/`,
  );
}

export async function createExecutorGroup(
  groupRequest: ExecutorGroupCreationRequest,
): Promise<ExecutorGroupWriteResponse> {
  return requestApi<ExecutorGroupWriteResponse>("/executor-groups/", {
    method: "POST",
    body: groupRequest,
  });
}

export async function updateExecutorGroup(
  groupId: string,
  changes: ExecutorGroupUpdateRequest,
): Promise<ExecutorGroupWriteResponse> {
  return requestApi<ExecutorGroupWriteResponse>(
    `/executor-groups/${encodeURIComponent(groupId)}/`,
    { method: "POST", body: changes },
  );
}

export async function deleteExecutorGroup(
  groupId: string,
): Promise<ExecutorGroupDeletionResponse> {
  const deletionRequest: ExecutorGroupDeletionRequest = {};
  return requestApi<ExecutorGroupDeletionResponse>(
    `/executor-groups/${encodeURIComponent(groupId)}/deletion/`,
    { method: "POST", body: deletionRequest },
  );
}
