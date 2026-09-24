// FileName: account.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";

import type {
  AccountAccessResponse,
  DepartmentAccessResponse,
  LoginRequest,
  MessageResponse,
  SessionResponse,
} from "./generated/browserApi";

function rejectInvalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}

function isNullableDate(value: unknown): value is string | null {
  return (
    value === null || (typeof value === "string" && Number.isFinite(Date.parse(value)))
  );
}

export function parseSessionResponse(payload: unknown): SessionResponse {
  if (!isRecord(payload) || !isRecord(payload.user)) return rejectInvalidResponse();
  const userInfo = payload.user;
  if (
    typeof userInfo.id !== "string" ||
    typeof userInfo.email !== "string" ||
    typeof userInfo.username !== "string" ||
    typeof payload.expires_at !== "string" ||
    !Number.isFinite(Date.parse(payload.expires_at)) ||
    typeof payload.csrf_token !== "string" ||
    !payload.csrf_token
  )
    return rejectInvalidResponse();
  return {
    user: {
      id: userInfo.id,
      email: userInfo.email,
      username: userInfo.username,
    },
    expires_at: payload.expires_at,
    csrf_token: payload.csrf_token,
  };
}

export function parseAccountAccessResponse(payload: unknown): AccountAccessResponse {
  if (!isRecord(payload) || !isRecord(payload.organization)) return rejectInvalidResponse();
  const organizationInfo = payload.organization;
  if (
    typeof organizationInfo.id !== "string" ||
    typeof organizationInfo.name !== "string" ||
    !isNullableDate(organizationInfo.suspended_at) ||
    !isNullableDate(organizationInfo.deletion_requested_at) ||
    !isNullableDate(organizationInfo.deletion_due_at) ||
    !isNullableDate(organizationInfo.deletion_started_at) ||
    typeof payload.is_org_admin !== "boolean" ||
    typeof payload.business_available !== "boolean" ||
    !Array.isArray(payload.departments)
  )
    return rejectInvalidResponse();
  const arrDepartment = payload.departments.map(
    (departmentInfo: unknown): DepartmentAccessResponse => {
      if (
        !isRecord(departmentInfo) ||
        typeof departmentInfo.id !== "string" ||
        typeof departmentInfo.name !== "string" ||
        typeof departmentInfo.path !== "string" ||
        (departmentInfo.role !== null &&
          departmentInfo.role !== "operator" &&
          departmentInfo.role !== "developer")
      )
        return rejectInvalidResponse();
      return {
        id: departmentInfo.id,
        name: departmentInfo.name,
        path: departmentInfo.path,
        role: departmentInfo.role,
      };
    },
  );
  return {
    organization: {
      id: organizationInfo.id,
      name: organizationInfo.name,
      suspended_at: organizationInfo.suspended_at,
      deletion_requested_at: organizationInfo.deletion_requested_at,
      deletion_due_at: organizationInfo.deletion_due_at,
      deletion_started_at: organizationInfo.deletion_started_at,
    },
    is_org_admin: payload.is_org_admin,
    business_available: payload.business_available,
    departments: arrDepartment,
  };
}

export async function getCurrentSession(): Promise<SessionResponse> {
  return parseSessionResponse(await requestApi("/auth/session/"));
}

export async function getAccountAccess(): Promise<AccountAccessResponse> {
  return parseAccountAccessResponse(await requestApi("/auth/access/"));
}

export async function signIn(
  email: string,
  password: string,
  rememberMe: boolean,
): Promise<SessionResponse> {
  const loginRequest: LoginRequest = { email, password, remember_me: rememberMe };
  return parseSessionResponse(
    await requestApi("/auth/login/", { method: "POST", body: loginRequest }),
  );
}

function parseMessageResponse(payload: unknown): MessageResponse {
  if (!isRecord(payload) || typeof payload.message !== "string")
    return rejectInvalidResponse();
  return { message: payload.message };
}

export async function signOut(): Promise<void> {
  parseMessageResponse(await requestApi("/auth/logout/", { method: "POST", body: {} }));
}
