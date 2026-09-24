# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, SecretStr

from console_project.contracts import JsonRequest, JsonResponsePayload


class LoginRequest(JsonRequest):
    email: str
    password: SecretStr
    remember_me: bool = False


class UserResponse(JsonResponsePayload):
    id: UUID
    email: str
    username: str


class SessionResponse(JsonResponsePayload):
    user: UserResponse
    expires_at: datetime
    csrf_token: Annotated[str, Field(min_length=1)]


class CsrfResponse(JsonResponsePayload):
    csrf_token: Annotated[str, Field(min_length=1)]
