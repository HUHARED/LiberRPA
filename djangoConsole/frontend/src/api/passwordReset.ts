// FileName: passwordReset.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  rejectInvalidResponse,
  parseMessageResponse,
} from "./responses";

import type { MessageResponse } from "./generated/browserApi";

export interface PasswordResetInfoResponse {
  email: string;
  expires_at: string;
}

export interface PasswordResetCompletionRequest {
  token: string;
  new_password: string;
  confirm_password: string;
}

export async function requestPasswordResetEmail(email: string): Promise<MessageResponse> {
  return parseMessageResponse(
    await requestApi("/auth/password/reset/email/", {
      method: "POST",
      body: { email },
    }),
  );
}

export async function checkPasswordReset(
  token: string,
): Promise<PasswordResetInfoResponse> {
  const payload = await requestApi("/auth/password/reset/check/", {
    method: "POST",
    body: { token },
  });
  if (
    !isRecord(payload) ||
    typeof payload.email !== "string" ||
    !payload.email ||
    !isDateString(payload.expires_at)
  )
    return rejectInvalidResponse();
  return { email: payload.email, expires_at: payload.expires_at };
}

export async function completePasswordReset(
  request: PasswordResetCompletionRequest,
): Promise<void> {
  parseMessageResponse(
    await requestApi("/auth/password/reset/complete/", {
      method: "POST",
      body: request,
    }),
  );
}
