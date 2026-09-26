// FileName: invitations.ts

import { requestApi } from "./client";
import { isRecord, ApiError } from "./errors";
import { parseMessageResponse } from "./account";
import { parsePaginationResponse } from "./members";

import type {
  InvitationCompletionRequest,
  InvitationCreateRequest,
  InvitationDetailsResponse,
  InvitationResponse,
  InvitationDepartmentRoleResponse,
  InvitationEmailDeliveryResponse,
  InvitationListResponse,
  InvitationRegistrationResponse,
  InvitationTokenRequest,
} from "./generated/browserApi";

function rejectInvalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}

function isDate(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isNullableDate(value: unknown): value is string | null {
  return value === null || isDate(value);
}

function isDelivery(value: unknown): value is InvitationEmailDeliveryResponse | null {
  return (
    value === null ||
    (isRecord(value) &&
      typeof value.id === "string" &&
      typeof value.status === "string" &&
      ["pending", "sending", "accepted", "failed", "not_sent", "unknown"].includes(
        value.status,
      ) &&
      typeof value.reason_code === "string" &&
      isNullableDate(value.attempted_at) &&
      isNullableDate(value.finished_at))
  );
}

function isInvitation(value: unknown): value is InvitationResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.email === "string" &&
    typeof value.is_org_admin === "boolean" &&
    typeof value.notes === "string" &&
    typeof value.status === "string" &&
    ["pending", "expired", "accepted", "revoked"].includes(value.status) &&
    isDate(value.created_at) &&
    isDate(value.requested_at) &&
    isDate(value.expires_at) &&
    isDate(value.resend_available_at) &&
    isNullableDate(value.accepted_at) &&
    isNullableDate(value.revoked_at) &&
    isDelivery(value.email_delivery) &&
    Array.isArray(value.department_roles) &&
    value.department_roles.every(
      (assignment: unknown): assignment is InvitationDepartmentRoleResponse =>
        isRecord(assignment) &&
        typeof assignment.department_id === "string" &&
        typeof assignment.department_name === "string" &&
        typeof assignment.department_path === "string" &&
        typeof assignment.department_deleted === "boolean" &&
        (assignment.role === "developer" || assignment.role === "operator"),
    )
  );
}

export function parseInvitationDetailsResponse(
  payload: unknown,
): InvitationDetailsResponse {
  if (!isRecord(payload) || !isInvitation(payload.invitation))
    return rejectInvalidResponse();
  return { invitation: payload.invitation };
}

export function parseInvitationListResponse(payload: unknown): InvitationListResponse {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.invitations) ||
    !payload.invitations.every(isInvitation)
  )
    return rejectInvalidResponse();
  return {
    invitations: payload.invitations,
    pagination: parsePaginationResponse(payload.pagination),
  };
}

export async function getInvitationList(
  pageNumber: number = 1,
): Promise<InvitationListResponse> {
  return parseInvitationListResponse(
    await requestApi(
      `/organization/invitations/?${new URLSearchParams({ page: String(pageNumber) })}`,
    ),
  );
}

export async function getInvitationDetails(
  invitationId: string,
): Promise<InvitationDetailsResponse> {
  return parseInvitationDetailsResponse(
    await requestApi(`/organization/invitations/${encodeURIComponent(invitationId)}/`),
  );
}

export async function createInvitation(
  request: InvitationCreateRequest,
): Promise<InvitationDetailsResponse> {
  return parseInvitationDetailsResponse(
    await requestApi("/organization/invitations/", { method: "POST", body: request }),
  );
}

export async function updateInvitation(
  invitationId: string,
  action: "resend" | "revoke",
): Promise<InvitationDetailsResponse> {
  return parseInvitationDetailsResponse(
    await requestApi(
      `/organization/invitations/${encodeURIComponent(invitationId)}/${action}/`,
      { method: "POST", body: {} },
    ),
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
  parseMessageResponse(
    await requestApi("/auth/invitation/complete/", { method: "POST", body: request }),
  );
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
