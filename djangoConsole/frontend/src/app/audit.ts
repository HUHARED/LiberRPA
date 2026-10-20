// FileName: audit.ts

import { ARR_AUDIT_RESULT_VALUE, type AuditChannel } from "../api/generated/browserApi";

export const AUDIT_CHANNEL_LABEL: Record<AuditChannel, string> = {
  session: "Web",
  editor: "Editor",
  executor: "Executor",
  api_key: "API Key",
  system: "System",
};

const AUDIT_TERM_LABEL: Record<string, string> = {
  api: "API",
  id: "ID",
  ids: "IDs",
  apikey: "API Key",
  dataqueue: "Data Queue",
  executorgroup: "Executor Group",
  executorsession: "Executor Session",
  memberinvitation: "Member Invitation",
  servicesettings: "Service Settings",
};

export function formatAuditLabel(value: string): string {
  return value
    .split(/[._]/)
    .map((word) => AUDIT_TERM_LABEL[word] ?? word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export const ARR_AUDIT_RESULT = ARR_AUDIT_RESULT_VALUE.map((value) => ({
  title: formatAuditLabel(value),
  value,
}));
