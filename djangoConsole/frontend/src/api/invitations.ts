// FileName: invitations.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse } from "./responses";

import type {
  InvitationCompletionRequest,
  InvitationCreateRequest,
  InvitationDetailsResponse,
  InvitationResponse,
  InvitationEmailDeliveryResponse,
  InvitationListResponse,
  InvitationRegistrationResponse,
  InvitationTokenRequest,
} from "./generated/browserApi";

export async function getInvitationList(
  pageNumber: number = 1,
): Promise<InvitationListResponse> {
  return requestApi<InvitationListResponse>(
    `/organization/invitations/?${new URLSearchParams({ page: String(pageNumber) })}`,
  );
}

export async function getInvitationDetails(
  invitationId: string,
): Promise<InvitationDetailsResponse> {
  return requestApi<InvitationDetailsResponse>(
    `/organization/invitations/${encodeURIComponent(invitationId)}/`,
  );
}

export async function createInvitation(
  request: InvitationCreateRequest,
): Promise<InvitationDetailsResponse> {
  return requestApi<InvitationDetailsResponse>("/organization/invitations/", {
    method: "POST",
    body: request,
  });
}

export async function updateInvitation(
  invitationId: string,
  action: "resend" | "revoke",
): Promise<InvitationDetailsResponse> {
  return requestApi<InvitationDetailsResponse>(
    `/organization/invitations/${encodeURIComponent(invitationId)}/${action}/`,
    { method: "POST", body: {} },
  );
}

export async function checkInvitation(
  token: string,
): Promise<InvitationRegistrationResponse> {
  const request: InvitationTokenRequest = { token };
  const payload = await requestApi("/auth/invitation/check/", {
    method: "POST",
    body: request,
  });
  if (
    !isRecord(payload) ||
    typeof payload.email !== "string" ||
    typeof payload.organization_name !== "string"
  )
    return rejectInvalidResponse();
  return { email: payload.email, organization_name: payload.organization_name };
}

export async function completeInvitation(
  request: InvitationCompletionRequest,
): Promise<void> {
  await requestApi("/auth/invitation/complete/", { method: "POST", body: request });
}

export function getInvitationStatus(
  invitation: InvitationResponse,
  currentTimeMs: number,
): InvitationResponse["status"] {
  return invitation.status === "pending" &&
    Date.parse(invitation.expires_at) <= currentTimeMs
    ? "expired"
    : invitation.status;
}

export function getDeliveryLabel(delivery: InvitationEmailDeliveryResponse | null): string {
  if (!delivery) return "Not queued";
  return {
    pending: "Queued",
    sending: "Sending",
    accepted: "Accepted by SMTP",
    failed: "Failed",
    not_sent: "Not sent",
    unknown: "Unknown",
  }[delivery.status];
}
