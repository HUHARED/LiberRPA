# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field, SecretStr

from console_project.contracts import JsonRequest, JsonResponsePayload


class BrowserMessageType(StrEnum):
    READY = "ready"
    SESSION_CHANGED = "session_changed"
    NOTIFICATIONS_CHANGED = "notifications_changed"


class BrowserEventResponse(JsonResponsePayload):
    type: BrowserMessageType


class LoginRequest(JsonRequest):
    email: str
    password: SecretStr
    remember_me: bool = False


class PlatformLoginRequest(JsonRequest):
    platform_login: str
    password: SecretStr
    remember_me: bool = False


class UserResponse(JsonResponsePayload):
    id: UUID
    email: str
    username: str


class SessionUserResponse(UserResponse):
    platform_login: str
    time_zone: str
    is_platform_admin: bool


class SessionResponse(JsonResponsePayload):
    user: SessionUserResponse
    expires_at: datetime
    csrf_token: Annotated[str, Field(min_length=1)]


class CsrfResponse(JsonResponsePayload):
    csrf_token: Annotated[str, Field(min_length=1)]


class ProfileUpdateRequest(JsonRequest):
    username: str
    time_zone: str


class ProfileWriteResponse(JsonResponsePayload):
    user: SessionUserResponse


class PasswordChangeRequest(JsonRequest):
    current_password: SecretStr
    new_password: SecretStr
    confirm_password: SecretStr


class SessionRevocationRequest(JsonRequest):
    current_password: SecretStr


class EmailChangeEmailRequest(JsonRequest):
    current_password: SecretStr
    new_email: str


class EmailChangeTokenRequest(JsonRequest):
    token: SecretStr


class EmailChangeInfoResponse(JsonResponsePayload):
    new_email: str
    expires_at: datetime


class AccountDeletionRequest(JsonRequest):
    current_password: SecretStr


class AccountDeletionBlockerResponse(JsonResponsePayload):
    code: Literal["last_org_admin"]


class AccountDeletionPreviewResponse(JsonResponsePayload):
    user: UserResponse
    can_delete: bool
    blockers: list[AccountDeletionBlockerResponse]


class ApiKeyStatus(TextChoices):
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"


class ApiKeyCreateRequest(JsonRequest):
    name: str
    expires_at: str
    notes: str = ""
    # Browser forms send local time with an explicit zone; other callers may send an ISO time with an offset.
    time_zone: str | None = None


class ApiKeyNotesRequest(JsonRequest):
    notes: str


class ApiKeyResponse(JsonResponsePayload):
    id: UUID
    name: str
    status: ApiKeyStatus = Field(strict=False)
    expires_at: datetime
    last_used_at: datetime | None
    notes: str
    created_at: datetime
    revoked_at: datetime | None


class ApiKeyWriteResponse(JsonResponsePayload):
    api_key: ApiKeyResponse


class ApiKeyCreationResponse(ApiKeyWriteResponse):
    secret: str = Field(min_length=1, repr=False)


class ApiKeyLimitsResponse(JsonResponsePayload):
    active_keys: int = Field(ge=0)
    inactive_retention_days: int = Field(ge=0)
    inactive_records: int = Field(ge=0)


class ApiKeyListResponse(JsonResponsePayload):
    api_keys: list[ApiKeyResponse]
    default_expires_at: datetime
    limits: ApiKeyLimitsResponse
