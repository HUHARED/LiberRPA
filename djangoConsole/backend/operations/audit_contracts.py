# FileName: audit_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field

from console_project.contracts import JsonResponsePayload, PaginationResponse


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
