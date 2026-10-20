// FileName: emailIssues.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  isNullableDateString,
  isNullableString,
  isNonnegativeInteger,
  parsePaginationResponse,
  rejectInvalidResponse,
} from "./responses";

import {
  ARR_EMAIL_STATUS,
  ARR_EMAIL_REASON_CODE,
  type EmailStatus,
  type EmailIssueResponse,
  type EmailIssueListResponse,
  type EmailIssueOrganizationResponse,
  type EmailIssueStatusResponse,
  type EmailIssueFiltersResponse,
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

  const payload = await requestApi(`/platform/email-issues/?${parameters}`);
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.issues) ||
    !payload.issues.every(
      (issue: unknown): issue is EmailIssueResponse =>
        isRecord(issue) &&
        typeof issue.id === "string" &&
        isNullableString(issue.organization_id) &&
        typeof issue.organization_name === "string" &&
        typeof issue.email_type_label === "string" &&
        typeof issue.recipient === "string" &&
        ARR_EMAIL_STATUS.some((status) => status === issue.status) &&
        typeof issue.status_label === "string" &&
        isDateString(issue.created_at) &&
        isNullableDateString(issue.attempted_at) &&
        isDateString(issue.finished_at) &&
        ARR_EMAIL_REASON_CODE.some((code) => code === issue.reason_code) &&
        typeof issue.reason_text === "string",
    ) ||
    !isNonnegativeInteger(payload.failed_today) ||
    typeof payload.instance_time_zone !== "string" ||
    !isDateString(payload.today) ||
    !isDateString(payload.updated_at)
  )
    return rejectInvalidResponse();

  return {
    issues: payload.issues,
    pagination: parsePaginationResponse(payload.pagination),
    failed_today: payload.failed_today,
    instance_time_zone: payload.instance_time_zone,
    today: payload.today,
    updated_at: payload.updated_at,
  };
}

export async function getEmailIssueFilters(): Promise<EmailIssueFiltersResponse> {
  const payload = await requestApi("/platform/email-issues/filters/");
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.organizations) ||
    !payload.organizations.every(
      (organization: unknown): organization is EmailIssueOrganizationResponse =>
        isRecord(organization) &&
        isNullableString(organization.id) &&
        typeof organization.name === "string",
    ) ||
    !Array.isArray(payload.statuses) ||
    !payload.statuses.every(
      (option: unknown): option is EmailIssueStatusResponse =>
        isRecord(option) &&
        ARR_EMAIL_STATUS.some((status) => status === option.value) &&
        typeof option.label === "string",
    )
  )
    return rejectInvalidResponse();

  return { organizations: payload.organizations, statuses: payload.statuses };
}
