// FileName: registration.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse, parseMessageResponse } from "./responses";

import type { MessageResponse } from "./generated/browserApi";

export interface RegistrationInfoResponse {
  email: string;
}

export interface RegistrationCompletionRequest {
  token: string;
  username: string;
  password: string;
  organization_name: string;
}

export async function requestRegistrationEmail(email: string): Promise<MessageResponse> {
  return parseMessageResponse(
    await requestApi("/auth/registration/email/", {
      method: "POST",
      body: { email },
    }),
  );
}

export async function checkRegistration(token: string): Promise<RegistrationInfoResponse> {
  const payload = await requestApi("/auth/registration/check/", {
    method: "POST",
    body: { token },
  });
  if (!isRecord(payload) || typeof payload.email !== "string" || !payload.email)
    return rejectInvalidResponse();
  return { email: payload.email };
}

export async function completeRegistration(
  request: RegistrationCompletionRequest,
): Promise<void> {
  await requestApi("/auth/registration/complete/", {
    method: "POST",
    body: request,
  });
}
