// FileName: executors.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNonnegativeInteger,
  isNullableString,
  isDateString,
  isNullableDateString,
  rejectInvalidResponse,
  parsePaginationResponse,
} from "./responses";

import {
  PackagePreparationState,
  ARR_EXECUTOR_ASSOCIATION_STATUS,
  type ExecutorCreationRequest,
  type ExecutorDeletionRequest,
  type ExecutorDetailsResponse,
  type ExecutorPreparationEntryResponse,
  type ExecutorGroupReferenceResponse,
  type ExecutorScheduleReferenceResponse,
  type ExecutorDispatchRequest,
  type ExecutorListEntryResponse,
  type ExecutorListResponse,
  type ExecutorUnassociateRequest,
  type ExecutorUpdateRequest,
  type ExecutorUpdateResponse,
  type ExecutorRecordResponse,
} from "./generated/browserApi";

export interface ExecutorListFilters {
  name: string;
  departmentIds: string[];
  dispatchStates: boolean[];
}

export function isExecutorScheduleReference(
  value: unknown,
): value is ExecutorScheduleReferenceResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.enabled === "boolean"
  );
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
    ARR_EXECUTOR_ASSOCIATION_STATUS.some((status) => status === value.association_status) &&
    isNullableString(value.session_id) &&
    (value.account === null ||
      (isRecord(value.account) &&
        typeof value.account.id === "string" &&
        typeof value.account.email === "string" &&
        typeof value.account.username === "string")) &&
    isNullableString(value.computer_name) &&
    isNullableString(value.client_version) &&
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
    !Array.isArray(payload.executor.referencing_schedules) ||
    !payload.executor.referencing_schedules.every(isExecutorScheduleReference) ||
    ![
      payload.executor.other_active_run_count,
      payload.executor.central_running_count,
      payload.executor.local_waiting_count,
    ].every((value) => value === null || isNonnegativeInteger(value)) ||
    !isNullableDateString(payload.executor.last_work_reported_at) ||
    !isRecord(payload.executor.preparation) ||
    !Array.isArray(payload.executor.preparation.items) ||
    !payload.executor.preparation.items.every(
      (preparation: unknown): preparation is ExecutorPreparationEntryResponse =>
        isRecord(preparation) &&
        typeof preparation.id === "string" &&
        typeof preparation.package_id === "string" &&
        typeof preparation.project_name === "string" &&
        typeof preparation.project_version === "string" &&
        typeof preparation.python_environment_name === "string" &&
        Object.values(PackagePreparationState).some(
          (state) => state === preparation.state,
        ) &&
        typeof preparation.reason === "string" &&
        isDateString(preparation.updated_at) &&
        typeof preparation.from_previous_association === "boolean",
    ) ||
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
      referencing_schedules: payload.executor.referencing_schedules,
      other_active_run_count: payload.executor.other_active_run_count as number | null,
      central_running_count: payload.executor.central_running_count as number | null,
      local_waiting_count: payload.executor.local_waiting_count as number | null,
      last_work_reported_at: payload.executor.last_work_reported_at,
      preparation: {
        items: payload.executor.preparation.items,
        ...parsePaginationResponse(payload.executor.preparation),
      },
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
  for (const strDepartmentId of filters.departmentIds)
    queryParameters.append("department_id", strDepartmentId);
  for (const boolDispatchEnabled of filters.dispatchStates)
    queryParameters.append("dispatch_enabled", String(boolDispatchEnabled));
  return parseExecutorListResponse(await requestApi(`/executors/?${queryParameters}`));
}

export async function getExecutorDetails(
  executorId: string,
  pageNumber = 1,
): Promise<ExecutorDetailsResponse> {
  const queryParameters = new URLSearchParams({ page: String(pageNumber) });
  return parseExecutorDetailsResponse(
    await requestApi(`/executors/${encodeURIComponent(executorId)}/?${queryParameters}`),
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
