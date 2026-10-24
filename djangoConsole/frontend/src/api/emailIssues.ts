// FileName: emailIssues.ts

import { requestApi } from "./client";

import type {
  EmailStatus,
  EmailIssueListResponse,
  EmailIssueFiltersResponse,
} from "./generated/browserApi";

export interface EmailIssueFilters {
  fromDate: string;
  toDate: string;
  organizationIds: string[];
  statuses: EmailStatus[];
}

export async function getEmailIssues(
  filters: EmailIssueFilters,
  pageNumber: number,
): Promise<EmailIssueListResponse> {
  const parameters = new URLSearchParams({ page: String(pageNumber) });
  if (filters.fromDate) parameters.set("date_from", filters.fromDate);
  if (filters.toDate) parameters.set("date_to", filters.toDate);
  for (const strOrganizationId of filters.organizationIds)
    parameters.append("organization_id", strOrganizationId);
  for (const status of filters.statuses) parameters.append("status", status);

  return requestApi<EmailIssueListResponse>(`/platform/email-issues/?${parameters}`);
}

export async function getEmailIssueFilters(): Promise<EmailIssueFiltersResponse> {
  return requestApi<EmailIssueFiltersResponse>("/platform/email-issues/filters/");
}
