// FileName: accountDeletion.ts

import { requestApi } from "./client";
import { isRecord, rejectInvalidResponse, parseMessageResponse } from "./responses";

import type {
  AccountDeletionPreviewResponse,
  AccountDeletionBlockerResponse,
  AccountDeletionRequest,
} from "./generated/browserApi";

export function parseAccountDeletionPreview(
  payload: unknown,
): AccountDeletionPreviewResponse {
  if (
    !isRecord(payload) ||
    !isRecord(payload.user) ||
    typeof payload.user.id !== "string" ||
    typeof payload.user.email !== "string" ||
    typeof payload.user.username !== "string" ||
    typeof payload.can_delete !== "boolean" ||
    !Array.isArray(payload.blockers) ||
    !payload.blockers.every(
      (blocker: unknown): blocker is AccountDeletionBlockerResponse =>
        isRecord(blocker) && blocker.code === "last_org_admin",
    ) ||
    payload.can_delete !== (payload.blockers.length === 0)
  )
    return rejectInvalidResponse();
  return {
    user: {
      id: payload.user.id,
      email: payload.user.email,
      username: payload.user.username,
    },
    can_delete: payload.can_delete,
    blockers: payload.blockers,
  };
}

function getDeletionPath(userId?: string): string {
  return userId === undefined
    ? "/auth/account/deletion/"
    : `/organization/members/${encodeURIComponent(userId)}/deletion/`;
}

export async function getAccountDeletionPreview(
  userId?: string,
): Promise<AccountDeletionPreviewResponse> {
  return parseAccountDeletionPreview(await requestApi(getDeletionPath(userId)));
}

export async function deleteAccount(password: string, userId?: string): Promise<void> {
  const deletionRequest: AccountDeletionRequest = { current_password: password };
  parseMessageResponse(
    await requestApi(getDeletionPath(userId), { method: "POST", body: deletionRequest }),
  );
}
