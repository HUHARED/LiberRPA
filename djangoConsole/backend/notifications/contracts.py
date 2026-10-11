# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from uuid import UUID

from pydantic import Field

from console_project.contracts import JsonRequest, JsonResponsePayload


class RecipientCreationRequest(JsonRequest):
    email: str = Field(min_length=1, max_length=254)
    notes: str = Field(default="", max_length=2000)


class RecipientNotesRequest(JsonRequest):
    notes: str = Field(max_length=2000)


class EmptyRequest(JsonRequest):
    pass


class RecipientTokenRequest(JsonRequest):
    token: str = Field(min_length=1, max_length=1000)


class RunEmailRecipientResponse(JsonResponsePayload):
    id: UUID
    email: str
    notes: str
    verified_at: datetime | None
    created_at: datetime


class RunEmailRecipientListResponse(JsonResponsePayload):
    recipients: list[RunEmailRecipientResponse]
    can_manage: bool


class RunEmailVerificationResponse(JsonResponsePayload):
    organization_name: str
    email: str
    verified: bool
