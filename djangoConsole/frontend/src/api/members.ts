// FileName: members.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";

import type {
  MemberDetailsResponse,
  MemberResponse,
  MemberDepartmentRoleResponse,
  MemberListResponse,
} from "./generated/browserApi";

function rejectInvalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isMember(value: unknown): value is MemberResponse {
  return (
    isRecord(value) &&
    isRecord(value.user) &&
    typeof value.user.id === "string" &&
    typeof value.user.email === "string" &&
    typeof value.user.username === "string" &&
    typeof value.is_org_admin === "boolean" &&
    Array.isArray(value.department_roles) &&
    value.department_roles.every(
      (assignment: unknown): assignment is MemberDepartmentRoleResponse =>
        isRecord(assignment) &&
        isRecord(assignment.department) &&
        typeof assignment.department.id === "string" &&
        typeof assignment.department.name === "string" &&
        typeof assignment.department.path === "string" &&
        (assignment.role === "developer" || assignment.role === "operator"),
    ) &&
    typeof value.notes === "string" &&
    typeof value.joined_at === "string" &&
    Number.isFinite(Date.parse(value.joined_at))
  );
}

export function parseMemberListResponse(payload: unknown): MemberListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.members) ||
    !payload.members.every(isMember) ||
    !isRecord(payload.pagination) ||
    !isNonnegativeInteger(payload.pagination.page) ||
    payload.pagination.page < 1 ||
    !isNonnegativeInteger(payload.pagination.page_size) ||
    payload.pagination.page_size < 1 ||
    !isNonnegativeInteger(payload.pagination.total_count) ||
    !isNonnegativeInteger(payload.pagination.total_pages) ||
    payload.pagination.total_pages < 1
  )
    return rejectInvalidResponse();
  return {
    members: payload.members,
    pagination: {
      page: payload.pagination.page,
      page_size: payload.pagination.page_size,
      total_count: payload.pagination.total_count,
      total_pages: payload.pagination.total_pages,
    },
  };
}

export function parseMemberDetailsResponse(payload: unknown): MemberDetailsResponse {
  if (!isRecord(payload) || !isMember(payload.member)) return rejectInvalidResponse();
  return { member: payload.member };
}

export async function getMemberList(pageNumber: number = 1): Promise<MemberListResponse> {
  const parameters = new URLSearchParams({ page: String(pageNumber) });
  return parseMemberListResponse(await requestApi(`/organization/members/?${parameters}`));
}

export async function getMemberDetails(userId: string): Promise<MemberDetailsResponse> {
  return parseMemberDetailsResponse(
    await requestApi(`/organization/members/${encodeURIComponent(userId)}/`),
  );
}
