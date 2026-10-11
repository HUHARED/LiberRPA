// FileName: runEmail.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse } from "./responses";

import type {
  RunEmailRecipientResponse,
  RunEmailRecipientListResponse,
  RunEmailVerificationResponse,
} from "./generated/browserApi";

export type RunEmailRecipient = RunEmailRecipientResponse;
export async function getRunEmailRecipients(
  status: "all" | "pending" | "verified" = "verified",
): Promise<RunEmailRecipientListResponse> {
  const response = await requestApi(
    `/run-email-recipients/?${new URLSearchParams({ status })}`,
  );
  if (
    !isRecord(response) ||
    !Array.isArray(response.recipients) ||
    !response.recipients.every(
      (value: unknown) =>
        isRecord(value) && typeof value.id === "string" && typeof value.email === "string",
    ) ||
    typeof response.can_manage !== "boolean"
  )
    return rejectInvalidResponse();
  return response as unknown as RunEmailRecipientListResponse;
}
export async function saveRunEmailRecipient(
  id: string | null,
  email: string,
  notes: string,
): Promise<void> {
  await requestApi(`/run-email-recipients/${id ? `${encodeURIComponent(id)}/` : ""}`, {
    method: "POST",
    body: id ? { notes } : { email, notes },
  });
}
export async function actOnRunEmailRecipient(
  id: string,
  action: "delete" | "resend",
): Promise<void> {
  await requestApi(`/run-email-recipients/${encodeURIComponent(id)}/${action}/`, {
    method: "POST",
    body: {},
  });
}
export async function verifyRunEmail(
  token: string,
  confirm = false,
): Promise<RunEmailVerificationResponse> {
  const response = await requestApi(
    `/run-email-recipients/verify/${confirm ? "" : `?${new URLSearchParams({ token })}`}`,
    confirm ? { method: "POST", body: { token } } : {},
  );
  if (
    !isRecord(response) ||
    typeof response.organization_name !== "string" ||
    typeof response.email !== "string" ||
    typeof response.verified !== "boolean"
  )
    return rejectInvalidResponse();
  return response as unknown as RunEmailVerificationResponse;
}
