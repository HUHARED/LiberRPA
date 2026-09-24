# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Literal
from uuid import UUID

from console_project.contracts import JsonResponsePayload


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
