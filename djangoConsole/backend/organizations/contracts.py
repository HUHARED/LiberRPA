# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator

from accounts.contracts import UserResponse
from console_project.contracts import JsonRequest, JsonResponsePayload


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
    role: Literal["developer", "operator"] | None


class AccountAccessResponse(JsonResponsePayload):
    organization: OrganizationAccessResponse
    is_org_admin: bool
    business_available: bool
    departments: list[DepartmentAccessResponse]


class OrganizationSettingsRequest(JsonRequest):
    name: str
    default_time_zone: str
    notes: str


class OrganizationSettingsRecordResponse(JsonResponsePayload):
    id: UUID
    name: str
    default_time_zone: str
    notes: str


class OrganizationSettingsResponse(JsonResponsePayload):
    organization: OrganizationSettingsRecordResponse


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
    role: Literal["developer", "operator"]


class DepartmentDetailsResponse(JsonResponsePayload):
    department: DepartmentListEntryResponse
    members: list[DepartmentMemberResponse]


class DepartmentIdentityResponse(JsonResponsePayload):
    id: UUID
    name: str


class DepartmentDeletionBlockerResponse(JsonResponsePayload):
    code: Literal[
        "child_departments",
        "department_memberships",
        "executors",
        "executor_groups",
        "assets",
        "data_queues",
    ]
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
    role: Literal["developer", "operator"]


class MemberResponse(JsonResponsePayload):
    user: UserResponse
    is_org_admin: bool
    department_roles: list[MemberDepartmentRoleResponse]
    notes: str
    joined_at: datetime


class PaginationResponse(JsonResponsePayload):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_count: int = Field(ge=0)
    total_pages: int = Field(ge=1)


class MemberListResponse(JsonResponsePayload):
    members: list[MemberResponse]
    pagination: PaginationResponse


class MemberDetailsResponse(JsonResponsePayload):
    member: MemberResponse


class DepartmentRoleRequest(JsonRequest):
    department_id: Annotated[UUID, Field(strict=False)]
    role: Literal["developer", "operator"]


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
    role: Literal["developer", "operator"]


class InvitationEmailDeliveryResponse(JsonResponsePayload):
    id: UUID
    status: Literal["pending", "sending", "accepted", "failed", "not_sent", "unknown"]
    reason_code: str
    attempted_at: datetime | None
    finished_at: datetime | None


class InvitationResponse(JsonResponsePayload):
    id: UUID
    email: str
    is_org_admin: bool
    department_roles: list[InvitationDepartmentRoleResponse]
    notes: str
    status: Literal["pending", "expired", "accepted", "revoked"]
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
