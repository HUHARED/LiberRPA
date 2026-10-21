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
  user: "Account",
  apikey: "API Key",
  editorsession: "Editor Session",
  membership: "Member",
  dataqueue: "Data Queue",
  sharedfile: "Shared File",
  jobrequest: "Job Request",
  runemailrecipient: "Run Email Recipient",
  executorgroup: "Executor Group",
  executorsession: "Executor Session",
  memberinvitation: "Member Invitation",
  servicesettings: "Service Settings",
  maintenancestate: "Maintenance",
  backuprecord: "Backup",
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
