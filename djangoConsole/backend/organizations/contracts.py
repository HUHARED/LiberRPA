# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

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
