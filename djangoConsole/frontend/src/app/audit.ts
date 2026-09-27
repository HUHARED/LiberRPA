// FileName: audit.ts

import type { AuditRecordResponse } from "../api/generated/browserApi";

export const AUDIT_CHANNEL_LABEL: Record<AuditRecordResponse["channel"], string> = {
  session: "Web",
  executor: "Executor",
  api_key: "API Key",
  system: "System",
};

export const ARR_AUDIT_RESULT = [
  { title: "Succeeded", value: "succeeded" },
  { title: "Failed", value: "failed" },
];

const AUDIT_TERM_LABEL: Record<string, string> = {
  api: "API",
  id: "ID",
  ids: "IDs",
  apikey: "API Key",
  dataqueue: "Data Queue",
  executorgroup: "Executor Group",
  executorsession: "Executor Session",
  memberinvitation: "Member Invitation",
};

export function formatAuditLabel(value: string): string {
  return value
    .split(/[._]/)
    .map((word) => AUDIT_TERM_LABEL[word] ?? word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
