// FileName: departments.ts

import { requestApi } from "./client";
import { ApiError } from "./errors";
import { isRecord, rejectInvalidResponse } from "./responses";

import {
  ARR_DEPARTMENT_DELETION_BLOCKER_CODE,
  type DepartmentCreationRequest,
  type DepartmentDeletionPreviewResponse,
  type DepartmentDeletionBlockerResponse,
  type DepartmentIdentityResponse,
  type DepartmentDeletionRequest,
  type DepartmentDeletionResponse,
  type DepartmentDetailsResponse,
  type DepartmentListResponse,
  type DepartmentUpdateRequest,
  type DepartmentWriteResponse,
} from "./generated/browserApi";

function isDepartmentIdentity(value: unknown): value is DepartmentIdentityResponse {
  return isRecord(value) && typeof value.id === "string" && typeof value.name === "string";
}

export function parseDepartmentDeletionPreviewResponse(
  payload: unknown,
): DepartmentDeletionPreviewResponse {
  if (
    !isRecord(payload) ||
    !isDepartmentIdentity(payload.department) ||
    typeof payload.can_delete !== "boolean" ||
    !Array.isArray(payload.blockers) ||
    !payload.blockers.every(
      (blocker: unknown): blocker is DepartmentDeletionBlockerResponse =>
        isRecord(blocker) &&
        ARR_DEPARTMENT_DELETION_BLOCKER_CODE.some((code) => code === blocker.code) &&
        typeof blocker.count === "number" &&
        Number.isSafeInteger(blocker.count) &&
        blocker.count > 0,
    ) ||
    payload.can_delete !== (payload.blockers.length === 0)
  )
    return rejectInvalidResponse();
  return {
    department: payload.department,
    can_delete: payload.can_delete,
    blockers: payload.blockers,
  };
}

export function parseDepartmentDeletionResponse(
  payload: unknown,
): DepartmentDeletionResponse {
  if (
    !isRecord(payload) ||
    !isDepartmentIdentity(payload.department) ||
    !("deleted_at" in payload.department) ||
    typeof payload.department.deleted_at !== "string"
  )
    return rejectInvalidResponse();
  return {
    department: { ...payload.department, deleted_at: payload.department.deleted_at },
  };
}

export async function getDepartmentList(): Promise<DepartmentListResponse> {
  return requestApi<DepartmentListResponse>("/organization/departments/");
}

export async function getDepartmentDetails(
  departmentId: string,
): Promise<DepartmentDetailsResponse> {
  return requestApi<DepartmentDetailsResponse>(
    `/organization/departments/${encodeURIComponent(departmentId)}/`,
  );
}

export async function createDepartment(
  departmentRequest: DepartmentCreationRequest,
): Promise<DepartmentWriteResponse> {
  return requestApi<DepartmentWriteResponse>("/organization/departments/", {
    method: "POST",
    body: departmentRequest,
  });
}

export async function updateDepartment(
  departmentId: string,
  departmentRequest: DepartmentUpdateRequest,
): Promise<DepartmentWriteResponse> {
  return requestApi<DepartmentWriteResponse>(
    `/organization/departments/${encodeURIComponent(departmentId)}/`,
    { method: "POST", body: departmentRequest },
  );
}

export async function getDepartmentDeletionPreview(
  departmentId: string,
): Promise<DepartmentDeletionPreviewResponse> {
  return parseDepartmentDeletionPreviewResponse(
    await requestApi(
      `/organization/departments/${encodeURIComponent(departmentId)}/deletion/`,
    ),
  );
}

export async function deleteDepartment(
  departmentId: string,
): Promise<DepartmentDeletionResponse | DepartmentDeletionPreviewResponse> {
  const deletionRequest: DepartmentDeletionRequest = {};
  try {
    return parseDepartmentDeletionResponse(
      await requestApi(
        `/organization/departments/${encodeURIComponent(departmentId)}/deletion/`,
        { method: "POST", body: deletionRequest },
      ),
    );
  } catch (e) {
    if (
      e instanceof ApiError &&
      e.statusCode === 409 &&
      e.code === "department_deletion_blocked"
    ) {
      // Reuse the blockers checked during this deletion attempt instead of fetching them again.
      const preview = parseDepartmentDeletionPreviewResponse(e.responsePayload);
      if (preview.can_delete) return rejectInvalidResponse();
      return preview;
    }
    throw e;
  }
}
