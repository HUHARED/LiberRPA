// FileName: account.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNullableDateString,
  rejectInvalidResponse,
  parseMessageResponse,
} from "./responses";

import {
  ARR_DEPARTMENT_ROLE,
  type AccountAccessResponse,
  type DepartmentAccessResponse,
  type LoginRequest,
  type PlatformLoginRequest,
  type SessionUserResponse,
  type SessionResponse,
} from "./generated/browserApi";

export function parseSessionUserResponse(payload: unknown): SessionUserResponse {
  if (
    !isRecord(payload) ||
    typeof payload.id !== "string" ||
    typeof payload.email !== "string" ||
    typeof payload.platform_login !== "string" ||
    typeof payload.username !== "string" ||
    typeof payload.time_zone !== "string" ||
    !payload.time_zone ||
    typeof payload.is_platform_admin !== "boolean"
  )
    return rejectInvalidResponse();
  return {
    id: payload.id,
    email: payload.email,
    platform_login: payload.platform_login,
    username: payload.username,
    time_zone: payload.time_zone,
    is_platform_admin: payload.is_platform_admin,
  };
}

export function parseSessionResponse(payload: unknown): SessionResponse {
  if (
    !isRecord(payload) ||
    typeof payload.expires_at !== "string" ||
    !Number.isFinite(Date.parse(payload.expires_at)) ||
    typeof payload.csrf_token !== "string" ||
    !payload.csrf_token
  )
    return rejectInvalidResponse();
  return {
    user: parseSessionUserResponse(payload.user),
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
    !isNullableDateString(organizationInfo.suspended_at) ||
    !isNullableDateString(organizationInfo.deletion_requested_at) ||
    !isNullableDateString(organizationInfo.deletion_due_at) ||
    !isNullableDateString(organizationInfo.deletion_started_at) ||
    typeof payload.is_org_admin !== "boolean" ||
    typeof payload.business_available !== "boolean" ||
    !Array.isArray(payload.departments)
  )
    return rejectInvalidResponse();

  const arrDepartment = payload.departments.map(
    (departmentInfo: unknown): DepartmentAccessResponse => {
      if (!isRecord(departmentInfo)) return rejectInvalidResponse();
      const strRole =
        departmentInfo.role === null
          ? null
          : ARR_DEPARTMENT_ROLE.find((role) => role === departmentInfo.role);
      if (
        typeof departmentInfo.id !== "string" ||
        typeof departmentInfo.name !== "string" ||
        typeof departmentInfo.path !== "string" ||
        strRole === undefined
      )
        return rejectInvalidResponse();

      return {
        id: departmentInfo.id,
        name: departmentInfo.name,
        path: departmentInfo.path,
        role: strRole,
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

export async function signInPlatform(
  platformLogin: string,
  password: string,
  rememberMe: boolean,
): Promise<SessionResponse> {
  const loginRequest: PlatformLoginRequest = {
    platform_login: platformLogin,
    password,
    remember_me: rememberMe,
  };
  return parseSessionResponse(
    await requestApi("/platform/auth/login/", { method: "POST", body: loginRequest }),
  );
}

export async function signOut(): Promise<void> {
  parseMessageResponse(await requestApi("/auth/logout/", { method: "POST", body: {} }));
}
