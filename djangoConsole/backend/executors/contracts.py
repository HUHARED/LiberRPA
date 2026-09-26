# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Literal
from uuid import UUID

from accounts.contracts import UserResponse
from console_project.contracts import JsonResponsePayload


class ExecutorDepartmentResponse(JsonResponsePayload):
    id: UUID
    name: str
    path: str


class ExecutorListEntryResponse(JsonResponsePayload):
    id: UUID
    name: str
    department_id: UUID
    notes: str
    dispatch_enabled: bool
    created_at: datetime
    deleted_at: datetime | None
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
