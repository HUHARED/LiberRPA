// FileName: executors.ts

import { requestApi } from "./client";
import { isRecord, isNullableString, rejectInvalidResponse } from "./responses";

import type {
  ExecutorCreationRequest,
  ExecutorDeletionRequest,
  ExecutorDetailsResponse,
  ExecutorDispatchRequest,
  ExecutorListResponse,
  ExecutorUnassociateRequest,
  ExecutorUpdateRequest,
  ExecutorUpdateResponse,
  RunTargetOptionsResponse,
} from "./generated/browserApi";

export interface ExecutorListFilters {
  name: string;
  departmentIds: string[];
  dispatchStates: boolean[];
}

export async function getExecutorList(
  filters: ExecutorListFilters,
  pageNumber: number,
): Promise<ExecutorListResponse> {
  const queryParameters = new URLSearchParams({ page: String(pageNumber) });
  if (filters.name) queryParameters.set("name", filters.name);
  for (const strDepartmentId of filters.departmentIds)
    queryParameters.append("department_id", strDepartmentId);
  for (const boolDispatchEnabled of filters.dispatchStates)
    queryParameters.append("dispatch_enabled", String(boolDispatchEnabled));
  return requestApi<ExecutorListResponse>(`/executors/?${queryParameters}`);
}

export async function getRunTargetOptions(
  departmentId?: string,
): Promise<RunTargetOptionsResponse> {
  const strQuery = departmentId
    ? `?${new URLSearchParams({ department_id: departmentId })}`
    : "";
  return requestApi<RunTargetOptionsResponse>(`/run-target-options/${strQuery}`);
}

export async function getExecutorDetails(
  executorId: string,
  pageNumber = 1,
): Promise<ExecutorDetailsResponse> {
  const queryParameters = new URLSearchParams({ page: String(pageNumber) });
  const response = await requestApi(
    `/executors/${encodeURIComponent(executorId)}/?${queryParameters}`,
  );
  if (
    !isRecord(response) ||
    !isRecord(response.executor) ||
    typeof response.executor.id !== "string" ||
    !isNullableString(response.executor.session_id)
  )
    return rejectInvalidResponse();
  return response as unknown as ExecutorDetailsResponse;
}

export async function createExecutor(
  executorRequest: ExecutorCreationRequest,
): Promise<ExecutorUpdateResponse> {
  return requestApi<ExecutorUpdateResponse>("/executors/", {
    method: "POST",
    body: executorRequest,
  });
}

export async function deleteExecutor(executorId: string): Promise<ExecutorUpdateResponse> {
  const deletionRequest: ExecutorDeletionRequest = {};
  return requestApi<ExecutorUpdateResponse>(
    `/executors/${encodeURIComponent(executorId)}/deletion/`,
    { method: "POST", body: deletionRequest },
  );
}

export async function updateExecutor(
  executorId: string,
  changes: ExecutorUpdateRequest,
): Promise<ExecutorUpdateResponse> {
  return requestApi<ExecutorUpdateResponse>(
    `/executors/${encodeURIComponent(executorId)}/`,
    { method: "POST", body: changes },
  );
}

export async function setExecutorDispatch(
  executorId: string,
  dispatchEnabled: boolean,
): Promise<ExecutorUpdateResponse> {
  const dispatchRequest: ExecutorDispatchRequest = { dispatch_enabled: dispatchEnabled };
  return requestApi<ExecutorUpdateResponse>(
    `/executors/${encodeURIComponent(executorId)}/dispatch/`,
    { method: "POST", body: dispatchRequest },
  );
}

export async function unassociateExecutor(
  executorId: string,
  sessionId: string,
): Promise<ExecutorUpdateResponse> {
  const unassociateRequest: ExecutorUnassociateRequest = { session_id: sessionId };
  return requestApi<ExecutorUpdateResponse>(
    `/executors/${encodeURIComponent(executorId)}/unassociate/`,
    { method: "POST", body: unassociateRequest },
  );
}
