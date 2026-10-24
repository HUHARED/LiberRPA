// FileName: runEmail.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse } from "./responses";

import type {
  RunEmailRecipientStatus,
  RunEmailRecipientResponse,
  RunEmailRecipientListResponse,
  RunEmailVerificationResponse,
  RunEmailSettingsResponse,
} from "./generated/browserApi";

export type RunEmailRecipient = RunEmailRecipientResponse;
export type { RunEmailRecipientStatus };
export type RunEmailRecipientFilter = RunEmailRecipientStatus | "all" | "eligible";

export type RunEmailEventKey = Exclude<keyof RunEmailSettingsResponse, "recipient_ids">;
export type RunEmailTemplates = Record<
  RunEmailEventKey,
  Pick<RunEmailSettingsResponse["on_start"], "subject" | "body">
>;

export async function getRunEmailTemplates(): Promise<RunEmailTemplates> {
  const response = await requestApi<{ defaults: RunEmailTemplates }>(
    "/run-email-recipients/templates/",
  );
  return response.defaults;
}

export async function getRunEmailRecipients(
  status: RunEmailRecipientFilter = "eligible",
): Promise<RunEmailRecipientListResponse> {
  return requestApi<RunEmailRecipientListResponse>(
    `/run-email-recipients/?${new URLSearchParams({ status })}`,
  );
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
