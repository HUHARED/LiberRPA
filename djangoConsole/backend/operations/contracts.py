# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field

from console_project.contracts import JsonRequest, JsonResponsePayload, PaginationResponse
from organizations.limits import OrganizationLimit, LimitUnit


class AuditChannel(TextChoices):
    SESSION = "session", "Web"
    EDITOR = "editor", "Editor"
    EXECUTOR = "executor", "Executor"
    API_KEY = "api_key", "API Key"
    SYSTEM = "system", "System"


class AuditResult(TextChoices):
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class AuditStage(TextChoices):
    OPERATION = "operation", "Operation"
    REQUEST = "request", "Request"


class AuditRecordResponse(JsonResponsePayload):
    id: UUID
    created_at: datetime
    actor_id: UUID | None
    actor_name: str
    channel: AuditChannel = Field(strict=False)
    module: str
    action: str
    object_type: str
    object_id: str
    object_name: str
    result: AuditResult = Field(strict=False)


class AuditListResponse(JsonResponsePayload):
    records: list[AuditRecordResponse]
    pagination: PaginationResponse


class AuditActorResponse(JsonResponsePayload):
    id: UUID | None
    name: str


class AuditFilterOptionsResponse(JsonResponsePayload):
    actors: list[AuditActorResponse]
    modules: list[str]
    actions: list[str]


class AuditChangeResponse(JsonResponsePayload):
    field: str
    # Null means the value was not recorded; a recorded JSON null is the text "null".
    before: str | None
    after: str | None


class AuditDetailsRecordResponse(AuditRecordResponse):
    organization_id: UUID
    organization_name: str
    department_id: UUID | None
    request_id: UUID | None
    stage: AuditStage = Field(strict=False)
    reason_code: str | None
    http_status: int | None
    changes: list[AuditChangeResponse]
    details_omitted: bool


class AuditDetailsResponse(JsonResponsePayload):
    record: AuditDetailsRecordResponse


class PlatformOrganizationStatus(TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    DELETION_SCHEDULED = "deletion_scheduled", "Deletion Scheduled"
    DELETION_IN_PROGRESS = "deletion_in_progress", "Deletion in Progress"


class PlatformAdministratorResponse(JsonResponsePayload):
    id: UUID
    name: str
    email: str


class PlatformOrganizationResponse(JsonResponsePayload):
    id: UUID
    name: str
    notes: str
    created_at: datetime
    administrators: list[PlatformAdministratorResponse]
    suspended_at: datetime | None
    deletion_requested_at: datetime | None
    deletion_started_at: datetime | None


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
