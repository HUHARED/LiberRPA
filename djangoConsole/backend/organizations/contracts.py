# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field, SecretStr, field_validator

from accounts.contracts import UserResponse
from console_project.contracts import JsonRequest, JsonResponsePayload, PaginationResponse
from notifications.contracts import EmailStatus, EmailReasonCode


class DepartmentRole(TextChoices):
    """The two roles that can be explicitly assigned within a department."""

    DEVELOPER = "developer", "Developer"
    OPERATOR = "operator", "Operator"


class DepartmentDeletionBlockerCode(StrEnum):
    CHILD_DEPARTMENTS = "child_departments"
    DEPARTMENT_MEMBERSHIPS = "department_memberships"
    EXECUTORS = "executors"
    EXECUTOR_GROUPS = "executor_groups"
    ASSETS = "assets"
    DATA_QUEUES = "data_queues"
    SHARED_FILES = "shared_files"
    FILE_UPLOADS = "file_uploads"
    PACKAGES = "packages"
    PACKAGE_UPLOADS = "package_uploads"
    SCHEDULES = "schedules"
    ACTIVE_JOBS = "active_jobs"


class InvitationStatus(TextChoices):
    PENDING = "pending", "Pending"
    EXPIRED = "expired", "Expired"
    ACCEPTED = "accepted", "Accepted"
    REVOKED = "revoked", "Revoked"


class OrganizationAccessResponse(JsonResponsePayload):
    id: UUID
    name: str
    suspended_at: datetime | None
    deletion_requested_at: datetime | None
    deletion_due_at: datetime | None
    deletion_started_at: datetime | None


class DepartmentAccessResponse(JsonResponsePayload):
    id: UUID
    name: str
    path: str
    role: DepartmentRole | None = Field(strict=False)


class AccountAccessResponse(JsonResponsePayload):
    organization: OrganizationAccessResponse
    is_org_admin: bool
    business_available: bool
    departments: list[DepartmentAccessResponse]


class OrganizationSettingsRequest(JsonRequest):
    name: str
    default_time_zone: str
    notes: str


class OrganizationRetentionRequest(JsonRequest):
    run_log_days: int


class OrganizationSettingsRecordResponse(JsonResponsePayload):
    id: UUID
    name: str
    default_time_zone: str
    notes: str


class OrganizationSettingsResponse(JsonResponsePayload):
    organization: OrganizationSettingsRecordResponse


class OrganizationDeletionRequest(JsonRequest):
    current_password: SecretStr


class OrganizationDeletionResponse(JsonResponsePayload):
    organization: OrganizationAccessResponse
    is_org_admin: bool
    business_available: bool
    can_schedule_deletion: bool
    can_cancel_deletion: bool
    deletion_delay_days: int = Field(ge=1)


class DepartmentUpdateRequest(JsonRequest):
    name: str
    parent_id: Annotated[UUID, Field(strict=False)] | None
    notes: str


class DepartmentCreationRequest(DepartmentUpdateRequest):
    parent_id: Annotated[UUID, Field(strict=False)] | None = None
    notes: str = ""


class DepartmentDeletionRequest(JsonRequest):
    """The URL selects the department; the server resolves all deletion conditions."""


class DepartmentRecordResponse(JsonResponsePayload):
    id: UUID
    name: str
    parent_id: UUID | None
    notes: str


class DepartmentWriteResponse(JsonResponsePayload):
    department: DepartmentRecordResponse


class DepartmentListEntryResponse(DepartmentRecordResponse):
    path: str


class DepartmentListResponse(JsonResponsePayload):
    departments: list[DepartmentListEntryResponse]


class DepartmentMemberResponse(JsonResponsePayload):
    user: UserResponse
    role: DepartmentRole = Field(strict=False)


class DepartmentDetailsResponse(JsonResponsePayload):
    department: DepartmentListEntryResponse
    members: list[DepartmentMemberResponse]


class DepartmentIdentityResponse(JsonResponsePayload):
    id: UUID
    name: str


class DepartmentDeletionBlockerResponse(JsonResponsePayload):
    code: DepartmentDeletionBlockerCode = Field(strict=False)
    count: int = Field(gt=0)


class DepartmentDeletionPreviewResponse(JsonResponsePayload):
    department: DepartmentIdentityResponse
    can_delete: bool
    blockers: list[DepartmentDeletionBlockerResponse]


class DeletedDepartmentResponse(DepartmentIdentityResponse):
    deleted_at: datetime


class DepartmentDeletionResponse(JsonResponsePayload):
    department: DeletedDepartmentResponse


class MemberDepartmentResponse(DepartmentIdentityResponse):
    path: str


class MemberDepartmentRoleResponse(JsonResponsePayload):
    department: MemberDepartmentResponse
    role: DepartmentRole = Field(strict=False)


class MemberResponse(JsonResponsePayload):
    user: UserResponse
    is_org_admin: bool
    department_roles: list[MemberDepartmentRoleResponse]
    notes: str
    joined_at: datetime


class MemberListResponse(JsonResponsePayload):
    members: list[MemberResponse]
    pagination: PaginationResponse


class MemberDetailsResponse(JsonResponsePayload):
    member: MemberResponse


class DepartmentRoleRequest(JsonRequest):
    department_id: Annotated[UUID, Field(strict=False)]
    role: DepartmentRole = Field(strict=False)


class MembershipUpdateRequest(JsonRequest):
    is_org_admin: bool
    # NOTE: Submit the full explicit role list even while OrgAdmin hides it in the form.
    department_roles: list[DepartmentRoleRequest]
    notes: str

    @field_validator("department_roles")
    @classmethod
    def validate_department_roles(
        cls, departmentRoles: list[DepartmentRoleRequest]
    ) -> list[DepartmentRoleRequest]:
        if len({roleRequest.department_id for roleRequest in departmentRoles}) != len(
            departmentRoles
        ):
            raise ValueError("Assign at most one role to each department.")
        return departmentRoles


class MembershipRecordResponse(JsonResponsePayload):
    user_id: UUID
    is_org_admin: bool
    department_roles: list[DepartmentRoleRequest]
    notes: str


class MembershipWriteResponse(JsonResponsePayload):
    member: MembershipRecordResponse


class InvitationCreateRequest(MembershipUpdateRequest):
    email: str


class InvitationTokenRequest(JsonRequest):
    token: SecretStr


class InvitationCompletionRequest(InvitationTokenRequest):
    password: SecretStr
    username: str = ""


class InvitationRegistrationResponse(JsonResponsePayload):
    email: str
    organization_name: str


class InvitationDepartmentRoleResponse(JsonResponsePayload):
    department_id: UUID
    department_name: str
    department_path: str
    department_deleted: bool
    role: DepartmentRole = Field(strict=False)


class InvitationEmailDeliveryResponse(JsonResponsePayload):
    id: UUID
    status: EmailStatus = Field(strict=False)
    reason_code: EmailReasonCode = Field(strict=False)
    attempted_at: datetime | None
    finished_at: datetime | None


class InvitationResponse(JsonResponsePayload):
    id: UUID
    email: str
    is_org_admin: bool
    department_roles: list[InvitationDepartmentRoleResponse]
    notes: str
    status: InvitationStatus = Field(strict=False)
    created_at: datetime
    requested_at: datetime
    expires_at: datetime
    resend_available_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    email_delivery: InvitationEmailDeliveryResponse | None


class InvitationDetailsResponse(JsonResponsePayload):
    invitation: InvitationResponse


class InvitationListResponse(JsonResponsePayload):
    invitations: list[InvitationResponse]
    pagination: PaginationResponse
