// FileName: departments.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";

import type {
  DepartmentCreationRequest,
  DepartmentListResponse,
  DepartmentListEntryResponse,
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

export function parseDepartmentListResponse(payload: unknown): DepartmentListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.departments) ||
    !payload.departments.every(
      (department: unknown): department is DepartmentListEntryResponse =>
        isRecord(department) &&
        isDepartmentRecord(department) &&
        typeof department.path === "string",
    )
  )
    return rejectInvalidResponse();
  return { departments: payload.departments };
}

export function parseDepartmentWriteResponse(payload: unknown): DepartmentWriteResponse {
  if (!isRecord(payload) || !isDepartmentRecord(payload.department))
    return rejectInvalidResponse();
  return { department: payload.department };
}

export async function getDepartmentList(): Promise<DepartmentListResponse> {
  return parseDepartmentListResponse(await requestApi("/organization/departments/"));
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
