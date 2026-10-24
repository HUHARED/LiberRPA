// FileName: members.ts

import { requestApi } from "./client";

import type {
  MemberDetailsResponse,
  MemberListResponse,
  MembershipUpdateRequest,
  MembershipWriteResponse,
} from "./generated/browserApi";

export async function getMemberList(pageNumber: number = 1): Promise<MemberListResponse> {
  const parameters = new URLSearchParams({ page: String(pageNumber) });
  return requestApi<MemberListResponse>(`/organization/members/?${parameters}`);
}

export async function getMemberDetails(userId: string): Promise<MemberDetailsResponse> {
  return requestApi<MemberDetailsResponse>(
    `/organization/members/${encodeURIComponent(userId)}/`,
  );
}

export async function updateMembership(
  userId: string,
  request: MembershipUpdateRequest,
): Promise<MembershipWriteResponse> {
  return requestApi<MembershipWriteResponse>(
    `/organization/members/${encodeURIComponent(userId)}/`,
    { method: "POST", body: request },
  );
}
