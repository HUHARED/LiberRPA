// FileName: runEmail.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse } from "./responses";

import { RunEmailRecipientStatus } from "./generated/browserApi";
import type {
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
  const response = await requestApi("/run-email-recipients/templates/");
  if (!isRecord(response) || !isRecord(response.defaults)) return rejectInvalidResponse();
  const defaults = response.defaults;
  if (
    !["on_start", "on_completed", "on_error"].every((key) => {
      const template = defaults[key];
      return (
        isRecord(template) &&
        typeof template.subject === "string" &&
        typeof template.body === "string"
      );
    })
  )
    return rejectInvalidResponse();
  return defaults as RunEmailTemplates;
}

export async function getRunEmailRecipients(
  status: RunEmailRecipientFilter = "eligible",
): Promise<RunEmailRecipientListResponse> {
  const response = await requestApi(
    `/run-email-recipients/?${new URLSearchParams({ status })}`,
  );
  if (
    !isRecord(response) ||
    !Array.isArray(response.recipients) ||
    !response.recipients.every(
      (value: unknown) =>
        isRecord(value) &&
        typeof value.id === "string" &&
        typeof value.email === "string" &&
        Object.values(RunEmailRecipientStatus).some((status) => status === value.status),
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
