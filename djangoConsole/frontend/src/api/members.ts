// FileName: members.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse, parsePaginationResponse } from "./responses";

import {
  ARR_DEPARTMENT_ROLE,
  type DepartmentRoleRequest,
  type MemberDetailsResponse,
  type MemberResponse,
  type MemberDepartmentRoleResponse,
  type MemberListResponse,
  type MembershipUpdateRequest,
  type MembershipWriteResponse,
} from "./generated/browserApi";

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
        ARR_DEPARTMENT_ROLE.some((role) => role === assignment.role),
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
    !payload.members.every(isMember)
  )
    return rejectInvalidResponse();
  return {
    members: payload.members,
    pagination: parsePaginationResponse(payload.pagination),
  };
}

export function parseMembershipWriteResponse(payload: unknown): MembershipWriteResponse {
  if (
    !isRecord(payload) ||
    !isRecord(payload.member) ||
    typeof payload.member.user_id !== "string" ||
    typeof payload.member.is_org_admin !== "boolean" ||
    typeof payload.member.notes !== "string" ||
    !Array.isArray(payload.member.department_roles) ||
    !payload.member.department_roles.every(
      (assignment: unknown): assignment is DepartmentRoleRequest =>
        isRecord(assignment) &&
        typeof assignment.department_id === "string" &&
        ARR_DEPARTMENT_ROLE.some((role) => role === assignment.role),
    )
  )
    return rejectInvalidResponse();
  return {
    member: {
      user_id: payload.member.user_id,
      is_org_admin: payload.member.is_org_admin,
      department_roles: payload.member.department_roles,
      notes: payload.member.notes,
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

export async function updateMembership(
  userId: string,
  request: MembershipUpdateRequest,
): Promise<MembershipWriteResponse> {
  return parseMembershipWriteResponse(
    await requestApi(`/organization/members/${encodeURIComponent(userId)}/`, {
      method: "POST",
      body: request,
    }),
  );
}
