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


class ExecutorUpdateRequest(JsonRequest):
    name: str
    notes: str


class ExecutorDispatchRequest(JsonRequest):
    dispatch_enabled: bool


class ExecutorUnassociateRequest(JsonRequest):
    session_id: Annotated[UUID, Field(strict=False)]


class ExecutorDepartmentResponse(JsonResponsePayload):
    id: UUID
    name: str
    path: str


class ExecutorRecordResponse(JsonResponsePayload):
    id: UUID
    name: str
    department_id: UUID
    notes: str
    dispatch_enabled: bool
    created_at: datetime
    deleted_at: datetime | None


class ExecutorUpdateResponse(JsonResponsePayload):
    executor: ExecutorRecordResponse


class ExecutorListEntryResponse(ExecutorRecordResponse):
    department: ExecutorDepartmentResponse
    can_manage: bool
    association_status: Literal["unassociated", "online", "offline"]
    session_id: UUID | None
    account: UserResponse | None
    computer: str | None
    version: str | None
    last_seen_at: datetime | None


class ExecutorListResponse(JsonResponsePayload):
    executors: list[ExecutorListEntryResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int


class ExecutorGroupReferenceResponse(JsonResponsePayload):
    id: UUID
    name: str


class ExecutorDetailsEntryResponse(ExecutorListEntryResponse):
    executor_groups: list[ExecutorGroupReferenceResponse]


class ExecutorDetailsResponse(JsonResponsePayload):
    executor: ExecutorDetailsEntryResponse
