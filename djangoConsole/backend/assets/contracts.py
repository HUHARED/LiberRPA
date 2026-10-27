# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field, model_validator

from console_project.contracts import (
    JsonValue,
    JsonRequest,
    JsonResponsePayload,
    PaginationResponse,
)


class AssetType(TextChoices):
    TEXT = "text", "Text"
    INTEGER = "integer", "Integer"
    NUMBER = "number", "Number"
    BOOLEAN = "boolean", "Boolean"
    JSON = "json", "JSON"
    SECRET_TEXT = "secret_text", "Secret Text"
    CREDENTIAL = "credential", "Credential"


SECRET_ASSET_TYPES = (AssetType.SECRET_TEXT, AssetType.CREDENTIAL)


type OrdinaryAssetType = Literal[
    AssetType.TEXT,
    AssetType.INTEGER,
    AssetType.NUMBER,
    AssetType.BOOLEAN,
    AssetType.JSON,
]


class AssetDetailsRequest(JsonRequest):
    name: str
    notes: str = ""


class AssetCreationRequest(AssetDetailsRequest):
    department_id: Annotated[UUID, Field(strict=False)]
    asset_type: AssetType = Field(strict=False)
    value: JsonValue


class AssetUpdateRequest(JsonRequest):
    details: AssetDetailsRequest | None = None
    value: JsonValue = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        # Omission keeps the current value; an explicit JSON null replaces it.
        if self.details is None and "value" not in self.model_fields_set:
            raise ValueError("Provide asset details or a replacement value.")
        return self


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
    asset_type: AssetType = Field(strict=False)
    notes: str
    value_summary: str
    can_manage: bool
    can_edit_value: bool
    created_at: datetime
    updated_at: datetime


class AssetListResponse(PaginationResponse):
    assets: list[AssetEntryResponse]


class AssetReferenceKind(StrEnum):
    PACKAGE = "package"
    SCHEDULE = "schedule"


class AssetReferenceResponse(JsonResponsePayload):
    kind: AssetReferenceKind
    id: UUID
    name: str
    project_version: str | None = None


class AssetDetailsEntryResponse(AssetEntryResponse):
    # Secret values are omitted from the payload, including both Credential fields.
    value: JsonValue = None
    references: list[AssetReferenceResponse] = Field(default_factory=list)


class AssetDetailsResponse(JsonResponsePayload):
    asset: AssetDetailsEntryResponse


class AssetRuntimeValueResponse(JsonResponsePayload):
    value: JsonValue


class AssetCredentialResponse(JsonResponsePayload):
    username: str = Field(repr=False)
    password: str = Field(repr=False)
