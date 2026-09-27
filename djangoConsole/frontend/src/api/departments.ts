// FileName: departments.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";

import type {
  DepartmentCreationRequest,
  DepartmentDeletionPreviewResponse,
  DepartmentDeletionBlockerResponse,
  DepartmentIdentityResponse,
  DepartmentDeletionRequest,
  DepartmentDeletionResponse,
  DepartmentDetailsResponse,
  DepartmentListEntryResponse,
  DepartmentMemberResponse,
  DepartmentListResponse,
  DepartmentUpdateRequest,
  DepartmentWriteResponse,
  DepartmentRecordResponse,
} from "./generated/browserApi";

function rejectInvalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}

function isDepartmentRecord(value: unknown): value is DepartmentRecordResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    (value.parent_id === null || typeof value.parent_id === "string") &&
    typeof value.notes === "string"
  );
}

function isDepartmentIdentity(value: unknown): value is DepartmentIdentityResponse {
  return isRecord(value) && typeof value.id === "string" && typeof value.name === "string";
}

function isDepartmentListEntry(value: unknown): value is DepartmentListEntryResponse {
  return isDepartmentRecord(value) && "path" in value && typeof value.path === "string";
}

export function parseDepartmentListResponse(payload: unknown): DepartmentListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.departments) ||
    !payload.departments.every(isDepartmentListEntry)
  )
    return rejectInvalidResponse();
  return { departments: payload.departments };
}

export function parseDepartmentDetailsResponse(
  payload: unknown,
): DepartmentDetailsResponse {
  if (
    !isRecord(payload) ||
    !isDepartmentListEntry(payload.department) ||
    !Array.isArray(payload.members) ||
    !payload.members.every(
      (member: unknown): member is DepartmentMemberResponse =>
        isRecord(member) &&
        isRecord(member.user) &&
        typeof member.user.id === "string" &&
        typeof member.user.email === "string" &&
        typeof member.user.username === "string" &&
        (member.role === "developer" || member.role === "operator"),
    )
  )
    return rejectInvalidResponse();
  return { department: payload.department, members: payload.members };
}

export function parseDepartmentWriteResponse(payload: unknown): DepartmentWriteResponse {
  if (!isRecord(payload) || !isDepartmentRecord(payload.department))
    return rejectInvalidResponse();
  return { department: payload.department };
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
        (blocker.code === "child_departments" ||
          blocker.code === "department_memberships" ||
          blocker.code === "executors" ||
          blocker.code === "executor_groups" ||
          blocker.code === "assets" ||
          blocker.code === "data_queues") &&
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
  return parseDepartmentListResponse(await requestApi("/organization/departments/"));
}

export async function getDepartmentDetails(
  departmentId: string,
): Promise<DepartmentDetailsResponse> {
  return parseDepartmentDetailsResponse(
    await requestApi(`/organization/departments/${encodeURIComponent(departmentId)}/`),
  );
}

export async function createDepartment(
  departmentRequest: DepartmentCreationRequest,
): Promise<DepartmentWriteResponse> {
  return parseDepartmentWriteResponse(
    await requestApi("/organization/departments/", {
      method: "POST",
      body: departmentRequest,
    }),
  );
}

export async function updateDepartment(
  departmentId: string,
  departmentRequest: DepartmentUpdateRequest,
): Promise<DepartmentWriteResponse> {
  return parseDepartmentWriteResponse(
    await requestApi(`/organization/departments/${encodeURIComponent(departmentId)}/`, {
      method: "POST",
      body: departmentRequest,
    }),
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
