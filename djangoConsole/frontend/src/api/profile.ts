// FileName: profile.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse, parseMessageResponse } from "./responses";
import { parseSessionUserResponse } from "./account";

import type {
  ProfileUpdateRequest,
  ProfileWriteResponse,
  PasswordChangeRequest,
  SessionRevocationRequest,
  EmailChangeEmailRequest,
  EmailChangeTokenRequest,
  EmailChangeInfoResponse,
} from "./generated/browserApi";

export async function updateProfile(
  request: ProfileUpdateRequest,
): Promise<ProfileWriteResponse> {
  const payload = await requestApi("/auth/profile/", { method: "POST", body: request });
  if (!isRecord(payload)) return rejectInvalidResponse();
  return { user: parseSessionUserResponse(payload.user) };
}

export async function changePassword(request: PasswordChangeRequest): Promise<void> {
  parseMessageResponse(
    await requestApi("/auth/password/change/", { method: "POST", body: request }),
  );
}

export async function signOutOtherSessions(
  request: SessionRevocationRequest,
): Promise<void> {
  parseMessageResponse(
    await requestApi("/auth/sessions/logout-others/", { method: "POST", body: request }),
  );
}

export async function requestEmailChange(request: EmailChangeEmailRequest): Promise<void> {
  parseMessageResponse(
    await requestApi("/auth/email/change/email/", { method: "POST", body: request }),
  );
}

export async function checkEmailChange(token: string): Promise<EmailChangeInfoResponse> {
  const request: EmailChangeTokenRequest = { token };
  const payload = await requestApi("/auth/email/change/check/", {
    method: "POST",
    body: request,
  });
  if (
    !isRecord(payload) ||
    typeof payload.new_email !== "string" ||
    typeof payload.expires_at !== "string" ||
    !Number.isFinite(Date.parse(payload.expires_at))
  )
    return rejectInvalidResponse();
  return { new_email: payload.new_email, expires_at: payload.expires_at };
}

export async function confirmEmailChange(token: string): Promise<void> {
  const request: EmailChangeTokenRequest = { token };
  parseMessageResponse(
    await requestApi("/auth/email/change/confirm/", { method: "POST", body: request }),
  );
}
