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


class AuditAction(TextChoices):
    """Stable audit event identifiers with user-facing action labels."""

    ACCOUNT_LOGIN = "account.login", "Sign In"
    ACCOUNT_LOGOUT = "account.logout", "Sign Out"
    ACCOUNT_UPDATE_PROFILE = "account.update_profile", "Update Profile"
    ACCOUNT_CHANGE_PASSWORD = "account.change_password", "Change Password"
    ACCOUNT_RESET_PASSWORD = "account.reset_password", "Reset Password"
    ACCOUNT_REVOKE_SESSIONS = "account.revoke_sessions", "Revoke Other Sessions"
    ACCOUNT_REQUEST_EMAIL_CHANGE = "account.request_email_change", "Request Email Change"
    ACCOUNT_CHANGE_EMAIL = "account.change_email", "Change Email"
    ACCOUNT_DELETE = "account.delete", "Delete Account"

    PLATFORM_INITIALIZE = "platform.initialize", "Initialize Platform"
    PLATFORM_RESET_PASSWORD = "platform.reset_password", "Reset Platform Password"

    API_KEY_CREATE = "api_key.create", "Create API Key"
    API_KEY_UPDATE = "api_key.update", "Update API Key"
    API_KEY_REVOKE = "api_key.revoke", "Revoke API Key"

    EDITOR_SESSION_LOGIN = "editor_session.login", "Sign In to Editor"
    EDITOR_SESSION_LOGOUT = "editor_session.logout", "Sign Out of Editor"

    ORGANIZATION_CREATE = "organization.create", "Create Organization"
    ORGANIZATION_UPDATE = "organization.update", "Update Organization"
    ORGANIZATION_UPDATE_RETENTION = (
        "organization.update_retention",
        "Update Run Log Retention",
    )
    ORGANIZATION_SCHEDULE_DELETION = (
        "organization.schedule_deletion",
        "Schedule Organization Deletion",
    )
    ORGANIZATION_CANCEL_DELETION = (
        "organization.cancel_deletion",
        "Cancel Organization Deletion",
    )
    ORGANIZATION_START_DELETION = (
        "organization.start_deletion",
        "Start Organization Deletion",
    )
    ORGANIZATION_COMPLETE_DELETION = (
        "organization.complete_deletion",
        "Complete Organization Deletion",
    )
    ORGANIZATION_SUSPEND = "organization.suspend", "Suspend Organization Service"
    ORGANIZATION_RESUME = "organization.resume", "Resume Organization Service"
    ORGANIZATION_UPDATE_LIMITS = (
        "organization.update_limits",
        "Update Organization Limits",
    )

    MEMBERSHIP_UPDATE = "membership.update", "Update Member"

    INVITATION_CREATE = "invitation.create", "Create Member Invitation"
    INVITATION_RESEND = "invitation.resend", "Resend Member Invitation"
    INVITATION_REVOKE = "invitation.revoke", "Revoke Member Invitation"
    INVITATION_ACCEPT = "invitation.accept", "Accept Member Invitation"

    DEPARTMENT_CREATE = "department.create", "Create Department"
    DEPARTMENT_UPDATE = "department.update", "Update Department"
    DEPARTMENT_DELETE = "department.delete", "Delete Department"

    EXECUTOR_CREATE = "executor.create", "Create Executor"
    EXECUTOR_UPDATE = "executor.update", "Update Executor"
    EXECUTOR_SET_DISPATCH = "executor.set_dispatch", "Change Executor Dispatch"
    EXECUTOR_ASSOCIATE = "executor.associate", "Associate Executor"
    EXECUTOR_UNASSOCIATE = "executor.unassociate", "Unassociate Executor"
    EXECUTOR_DELETE = "executor.delete", "Delete Executor"

    EXECUTOR_GROUP_CREATE = "executor_group.create", "Create Executor Group"
    EXECUTOR_GROUP_UPDATE = "executor_group.update", "Update Executor Group"
    EXECUTOR_GROUP_DELETE = "executor_group.delete", "Delete Executor Group"

    EXECUTOR_SESSION_LOGIN = "executor_session.login", "Sign In to Executor"
    EXECUTOR_SESSION_LOGOUT = "executor_session.logout", "Sign Out of Executor"

    PACKAGES_UPLOAD = "packages.upload", "Upload Package"
    PACKAGES_UPDATE = "packages.update", "Update Package"
    PACKAGES_DOWNLOAD = "packages.download", "Download Package"
    PACKAGES_CANCEL_PREPARATION = (
        "packages.cancel_preparation",
        "Cancel Package Preparation",
    )
    PACKAGES_DELETE = "packages.delete", "Delete Package"

    SCHEDULE_CREATE = "schedule.create", "Create Schedule"
    SCHEDULE_UPDATE = "schedule.update", "Update Schedule"
    SCHEDULE_ENABLE = "schedule.enable", "Enable Schedule"
    SCHEDULE_DISABLE = "schedule.disable", "Disable Schedule"
    SCHEDULE_DELETE = "schedule.delete", "Delete Schedule"

    JOB_ACCEPT = "job.accept", "Accept Job Request"
    JOB_CANCEL = "job.cancel", "Cancel Job"
    JOB_STOP = "job.stop", "Request Job Stop"
    JOB_CLOSE = "job.close", "Close Job"

    RUN_STOP = "run.stop", "Request Run Stop"
    RUN_CLEAR_LOGS = "run.clear_logs", "Clear Run Logs"

    ASSET_CREATE = "asset.create", "Create Asset"
    ASSET_UPDATE = "asset.update", "Update Asset"
    ASSET_SET_VALUE = "asset.set_value", "Set Asset Value"
    ASSET_DELETE = "asset.delete", "Delete Asset"

    DATA_QUEUE_CREATE = "data_queue.create", "Create Data Queue"
    DATA_QUEUE_UPDATE = "data_queue.update", "Update Data Queue"
    DATA_QUEUE_UPLOAD = "data_queue.upload", "Upload Queue Items"
    DATA_QUEUE_CLAIM = "data_queue.claim", "Claim Queue Items"
    DATA_QUEUE_RESET = "data_queue.reset", "Reset Queue Items"
    DATA_QUEUE_DELETE_ITEMS = "data_queue.delete_items", "Delete Queue Items"
    DATA_QUEUE_DELETE = "data_queue.delete", "Delete Data Queue"

    SHARED_FILES_UPLOAD = "shared_files.upload", "Upload Shared File"
    SHARED_FILES_OVERWRITE = "shared_files.overwrite", "Overwrite Shared File"
    SHARED_FILES_DOWNLOAD = "shared_files.download", "Download Shared File"
    SHARED_FILES_DELETE = "shared_files.delete", "Delete Shared File"

    RUN_EMAIL_RECIPIENT_CREATE = "run_email_recipient.create", "Add Run Email Recipient"
    RUN_EMAIL_RECIPIENT_NOTES = (
        "run_email_recipient.notes",
        "Update Run Email Recipient Notes",
    )
    RUN_EMAIL_RECIPIENT_RESEND = (
        "run_email_recipient.resend",
        "Resend Run Email Verification",
    )
    RUN_EMAIL_RECIPIENT_VERIFY = (
        "run_email_recipient.verify",
        "Verify Run Email Recipient",
    )
    RUN_EMAIL_RECIPIENT_DELETE = (
        "run_email_recipient.delete",
        "Delete Run Email Recipient",
    )

    SERVICE_SETTINGS_UPDATE = "service_settings.update", "Update Service Settings"

    MAINTENANCE_ENTER = "maintenance.enter", "Enter Maintenance"
    MAINTENANCE_RESUME = "maintenance.resume", "Resume Service"

    BACKUP_REQUEST = "backup.request", "Request Backup"
    BACKUP_COMPLETE = "backup.complete", "Finish Backup"
    BACKUP_RESTORE = "backup.restore", "Restore Backup"


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
    action: AuditAction = Field(strict=False)
    object_type: str
    object_id: str
    object_name: str
    result: AuditResult = Field(strict=False)


class PlatformAuditRecordResponse(AuditRecordResponse):
    organization_id: UUID | None
    organization_name: str


class AuditListResponse(JsonResponsePayload):
    records: list[AuditRecordResponse]
    pagination: PaginationResponse


class PlatformAuditListResponse(JsonResponsePayload):
    records: list[PlatformAuditRecordResponse]
    pagination: PaginationResponse


class AuditActorResponse(JsonResponsePayload):
    id: UUID | None
    name: str


class PlatformAuditOrganizationResponse(JsonResponsePayload):
    id: UUID | None
    name: str


class AuditFilterOptionsResponse(JsonResponsePayload):
    actors: list[AuditActorResponse]
    modules: list[str]
    actions: list[Annotated[AuditAction, Field(strict=False)]]


class PlatformAuditFilterOptionsResponse(JsonResponsePayload):
    actors: list[AuditActorResponse]
    organizations: list[PlatformAuditOrganizationResponse]
    actions: list[Annotated[AuditAction, Field(strict=False)]]


class AuditChangeResponse(JsonResponsePayload):
    field: str
    # Null means the value was not recorded; a recorded JSON null is the text "null".
    before: str | None
    after: str | None


class AuditDetailsRecordResponse(AuditRecordResponse):
    organization_id: UUID | None
    organization_name: str
    department_id: UUID | None
    request_id: UUID | None
    stage: AuditStage = Field(strict=False)
    reason: str | None
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


class InstanceComponentResponse(JsonResponsePayload):
    component: InstanceComponent
    status: InstanceHealthStatus
    checked_at: datetime | None
    message: str


class InstanceStorageResponse(JsonResponsePayload):
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    status: InstanceHealthStatus
    checked_at: datetime
    message: str


class InstanceBackupResponse(JsonResponsePayload):
    ended_at: datetime
    data_as_of: datetime
    size_bytes: int


class InstanceSummaryResponse(JsonResponsePayload):
    version: str
    service_state: ServiceState | None
    maintenance_entered_at: datetime | None
    last_successful_backup: InstanceBackupResponse | None
    updated_at: datetime
    time_zone: str
    components: list[InstanceComponentResponse]
    storage: InstanceStorageResponse


class InstanceHistoryRange(TextChoices):
    HOUR = "1h", "Last Hour"
    DAY = "24h", "Last 24 Hours"
    WEEK = "7d", "Last 7 Days"
    FIFTEEN_DAYS = "15d", "Last 15 Days"


class InstanceMetricsResponse(JsonResponsePayload):
    cpu_percent: float | None
    memory_percent: float | None
    network_receive_bytes_per_second: float | None
    network_transmit_bytes_per_second: float | None


class InstanceHistorySampleResponse(InstanceMetricsResponse):
    timestamp: datetime


class InstanceStatusResponse(JsonResponsePayload):
    configured: bool
    range: InstanceHistoryRange = Field(strict=False)
    interval_seconds: int
    network_interfaces: list[str]
    network_interface: str | None
    collected_at: datetime | None
    current: InstanceMetricsResponse
    history: list[InstanceHistorySampleResponse]


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


class EmailIssueListResponse(JsonResponsePayload):
    issues: list[EmailIssueResponse]
    pagination: PaginationResponse
    failed_today: int
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
