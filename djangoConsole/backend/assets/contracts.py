# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from console_project.contracts import JsonValue, JsonRequest, JsonResponsePayload


MAX_ASSET_RUNTIME_BYTES = 2 * 1024 * 1024

type AssetType = Literal[
    "text", "integer", "number", "boolean", "json", "secret_text", "credential"
]


class AssetDetailsRequest(JsonRequest):
    name: str
    notes: str = ""


class AssetCreationRequest(AssetDetailsRequest):
    department_id: Annotated[UUID, Field(strict=False)]
    asset_type: AssetType
    value: JsonValue


class AssetValueRequest(JsonRequest):
    value: JsonValue


class AssetDeletionRequest(JsonRequest):
    pass


class AssetPathRequest(JsonRequest):
    path: Annotated[str, Field(min_length=1, max_length=16384)]


class AssetRuntimeValueRequest(AssetPathRequest):
    value: JsonValue


class AssetDepartmentResponse(JsonResponsePayload):
    id: UUID
    path: str


class AssetEntryResponse(JsonResponsePayload):
    id: UUID
    name: str
    department: AssetDepartmentResponse
    path: str
    asset_type: AssetType
    notes: str
    value_summary: str
    can_manage: bool
    can_edit_value: bool
    created_at: datetime
    updated_at: datetime


class AssetListResponse(JsonResponsePayload):
    assets: list[AssetEntryResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int


class AssetDetailsEntryResponse(AssetEntryResponse):
    # Secret values are omitted from the payload, including both Credential fields.
    value: JsonValue = None


class AssetDetailsResponse(JsonResponsePayload):
    asset: AssetDetailsEntryResponse


class AssetRuntimeValueResponse(JsonResponsePayload):
    value: JsonValue


class AssetCredentialResponse(JsonResponsePayload):
    username: str = Field(repr=False)
    password: str = Field(repr=False)
