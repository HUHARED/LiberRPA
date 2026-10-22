# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from django.db.models import TextChoices
from pydantic import AwareDatetime, Field, StringConstraints

from console_project.contracts import JsonRequest, JsonResponsePayload, PaginationResponse
from organizations.limits import OrganizationLimit, LimitUnit
from notifications.contracts import EmailStatus, EmailReasonCode


class PlatformOrganizationStatus(TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    DELETION_SCHEDULED = "deletion_scheduled", "Deletion Scheduled"
    DELETION_IN_PROGRESS = "deletion_in_progress", "Deletion in Progress"


class OrganizationAdministratorResponse(JsonResponsePayload):
    id: UUID
    name: str
    email: str


class PlatformOrganizationResponse(JsonResponsePayload):
    id: UUID
    name: str
    notes: str
    created_at: datetime
    administrators: list[OrganizationAdministratorResponse]
    suspended_at: datetime | None
    deletion_requested_at: datetime | None
    deletion_started_at: datetime | None


INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH = 500


class PlatformOrganizationDetailsResponse(PlatformOrganizationResponse):
    default_time_zone: str
    deletion_due_at: datetime | None


class OrganizationServiceRequest(JsonRequest):
    suspended: bool
    reason: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH,
            pattern=r"^[^\x00]+$",
        ),
    ]
    expected_suspended_at: Annotated[AwareDatetime, Field(strict=False)] | None
    expected_deletion_requested_at: Annotated[AwareDatetime, Field(strict=False)] | None


class PlatformOrganizationListResponse(JsonResponsePayload):
    organizations: list[PlatformOrganizationResponse]
    pagination: PaginationResponse


class PlatformOrganizationFilters(JsonRequest):
    page: int = Field(default=1, ge=1)
    name: str = Field(default="", max_length=200)
    organization_id: UUID | None = None
    status: list[PlatformOrganizationStatus] = Field(default_factory=list, max_length=4)


class OrganizationLimitResponse(JsonResponsePayload):
    key: OrganizationLimit
    label: str
    unit: LimitUnit
    used: int | None
    reserved: int | None
    limit: int
    default_limit: int
    override: int | None
    minimum: int
    maximum: int | None


class OrganizationLimitIdentityResponse(JsonResponsePayload):
    id: UUID
    name: str


class OrganizationRetentionResponse(JsonResponsePayload):
    run_log_days: int
    run_log_max_days: int
    run_history_days: int
    audit_days: int


class OrganizationLimitsResponse(JsonResponsePayload):
    organization: OrganizationLimitIdentityResponse
    limits: list[OrganizationLimitResponse]
    version: str
    updated_at: datetime
    retention: OrganizationRetentionResponse
    usage_warning: str | None


class OrganizationLimitsRequest(JsonRequest):
    version: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]+$")
    # The service validates the allowlisted keys and each limit's deployment rules once.
    overrides: dict[str, int]


class ServiceSettingsRequest(JsonRequest):
    allow_organization_creation: bool


class ServiceSettingsResponse(JsonResponsePayload):
    allow_organization_creation: bool
    console_url: str
    support_email: str


class ServiceState(TextChoices):
    NORMAL = "normal", "Normal"
    MAINTENANCE = "maintenance", "Maintenance"


class MaintenanceAction(TextChoices):
    ENTER = "enter", "Enter Maintenance"
    RESUME = "resume", "Resume Service"


class InstanceHealthStatus(TextChoices):
    HEALTHY = "healthy", "Healthy"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"
    UNKNOWN = "unknown", "Unknown"


class InstanceComponent(TextChoices):
    DATABASE = "database", "Database"
    SCHEDULER = "scheduler", "Scheduler"
    EMAIL = "email", "Email"
    CLEANUP = "cleanup", "Cleanup"
    BACKUP = "backup", "Backup"


class EmailIssueResponse(JsonResponsePayload):
    id: UUID
    organization_id: UUID | None
    organization_name: str
    email_type_label: str
    recipient: str
    status: EmailStatus = Field(strict=False)
    status_label: str
    created_at: datetime
    attempted_at: datetime | None
    finished_at: datetime
    reason_code: EmailReasonCode = Field(strict=False)
    reason_text: str


class EmailUsageResponse(JsonResponsePayload):
    smtp_budget_used_24h: int = Field(ge=0)
    smtp_budget_limit_24h: int = Field(ge=0)
    run_budget_used_24h: int = Field(ge=0)
    run_budget_limit_24h: int = Field(ge=0)
    accepted_by_smtp_24h: int = Field(ge=0)
    pending: int = Field(ge=0)


class EmailIssueListResponse(JsonResponsePayload):
    issues: list[EmailIssueResponse]
    pagination: PaginationResponse
    usage: EmailUsageResponse
    failed_today: int = Field(ge=0)
    time_zone: str
    today: date
    updated_at: datetime


class EmailIssueOrganizationResponse(JsonResponsePayload):
    id: UUID | None
    name: str


class EmailIssueStatusResponse(JsonResponsePayload):
    value: EmailStatus = Field(strict=False)
    label: str


class EmailIssueFiltersResponse(JsonResponsePayload):
    organizations: list[EmailIssueOrganizationResponse]
    statuses: list[EmailIssueStatusResponse]
