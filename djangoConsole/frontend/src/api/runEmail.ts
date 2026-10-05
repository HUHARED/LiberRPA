// FileName: runEmail.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse } from "./responses";

export interface RunEmailRecipient {
  id: string;
  email: string;
  notes: string;
  verified_at: string | null;
  created_at: string;
}
export async function getRunEmailRecipients(
  status = "verified",
): Promise<{ recipients: RunEmailRecipient[]; can_manage: boolean }> {
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
  return response as unknown as { recipients: RunEmailRecipient[]; can_manage: boolean };
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
): Promise<{ organization_name: string; email: string; verified: boolean }> {
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
  return response as unknown as {
    organization_name: string;
    email: string;
    verified: boolean;
  };
}
