// FileName: departments.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";

import type {
  DepartmentCreationRequest,
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
