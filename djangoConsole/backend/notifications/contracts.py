# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, model_validator

from console_project.contracts import JsonRequest, JsonResponsePayload
from console_project.validators import validate_json_string


INT_RUN_EMAIL_MAX_BYTES = 64 * 1024


class RunEmailOutputStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    LIMIT = "limit"
    UNAVAILABLE = "unavailable"


class RunEmailOutputValue(JsonRequest):
    key: str
    status: Annotated[RunEmailOutputStatus, Field(strict=False)]
    text: str

    @model_validator(mode="after")
    def validate_value(self) -> Self:
        validate_json_string(self.key)
        validate_json_string(self.text)
        if self.status == RunEmailOutputStatus.AVAILABLE:
            if not self.text:
                raise ValueError("Available email values require text.")
        elif self.text:
            raise ValueError("Unavailable email values cannot contain text.")
        return self


class RecipientCreationRequest(JsonRequest):
    email: str = Field(min_length=1, max_length=254)
    notes: str = Field(default="", max_length=2000)


class RecipientNotesRequest(JsonRequest):
    notes: str = Field(max_length=2000)


class EmptyRequest(JsonRequest):
    pass


class RecipientTokenRequest(JsonRequest):
    token: str = Field(min_length=1, max_length=1000)


class RunEmailRecipientStatus(StrEnum):
    MEMBER = "member"
    VERIFIED = "verified"
    PENDING = "pending"


class RunEmailRecipientResponse(JsonResponsePayload):
    id: UUID
    email: str
    notes: str
    status: RunEmailRecipientStatus
    verified_at: datetime | None
    created_at: datetime


class RunEmailRecipientListResponse(JsonResponsePayload):
    recipients: list[RunEmailRecipientResponse]
    can_manage: bool


class RunEmailVerificationResponse(JsonResponsePayload):
    organization_name: str
    email: str
    verified: bool
