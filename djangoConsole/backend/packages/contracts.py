# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, cast
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field, field_validator, model_validator

from assets.contracts import OrdinaryAssetType
from console_project.contracts import (
    JsonValue,
    JsonRequest,
    JsonResponsePayload,
    PaginationResponse,
)
from console_project.constants import INT_WINDOWS_NAME_MAX_LENGTH, RunLogLevel
from console_project.validators import validate_windows_name, validate_json_value
from notifications.contracts import INT_RUN_EMAIL_MAX_BYTES

MAX_PACKAGE_BYTES = 512 * 1024 * 1024

# NOTE: Keep these package limits aligned with Project Manager and Executor.
INT_DESCRIPTION_MAX_LENGTH = 2000
INT_VERSION_SUMMARY_MAX_LENGTH = 500
INT_CUSTOM_ARGUMENT_MAX_COUNT = 100
INT_CUSTOM_ARGUMENT_MAX_BYTES = 64 * 1024
INT_MAX_RETRY_COUNT = 3
INT_MAX_TIMEOUT_MIN = 35791

type RequestUuid = Annotated[UUID, Field(strict=False)]


class PackageReferenceKind(StrEnum):
    SCHEDULE = "schedule"
    JOB = "job"
    PREPARATION = "preparation"
    DOWNLOAD = "download"


class PackagePreparationState(TextChoices):
    PENDING = "pending", "Pending"
    PREPARING = "preparing", "Preparing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


type PackagePreparationResult = Literal[
    PackagePreparationState.READY, PackagePreparationState.FAILED
]


class RunConflictPolicy(StrEnum):
    SKIP = "skip"
    WAIT = "wait"
    CONCURRENT = "concurrent"


# NOTE: Declaration order determines dispatch priority.
class RunPriority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


RUN_PRIORITY_ORDER = tuple(RunPriority)


class OrdinaryAssetBinding(JsonRequest):
    name: str = Field(min_length=1, max_length=128)
    asset_type: OrdinaryAssetType


class RunEmailTemplate(JsonRequest):
    enabled: bool = False
    subject: str = Field(default="", max_length=256)
    body: str = Field(default="", max_length=INT_RUN_EMAIL_MAX_BYTES)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        if "\r" in value or "\n" in value or "\0" in value:
            raise ValueError("Enter a single-line subject.")
        return value


class RunEmailSettings(JsonRequest):
    recipient_ids: list[RequestUuid] = Field(default_factory=list, max_length=5)
    on_start: RunEmailTemplate = Field(default_factory=RunEmailTemplate)
    on_completed: RunEmailTemplate = Field(default_factory=RunEmailTemplate)
    on_error: RunEmailTemplate = Field(default_factory=RunEmailTemplate)


def build_default_run_email() -> dict:
    return RunEmailSettings().model_dump(mode="json")


def validate_custom_arguments(arguments: list[list[JsonValue]]) -> None:
    if len(arguments) > INT_CUSTOM_ARGUMENT_MAX_COUNT:
        raise ValueError(
            f"Custom Arguments must not contain more than {INT_CUSTOM_ARGUMENT_MAX_COUNT} entries."
        )
    validate_json_value(cast(JsonValue, arguments))
    if (
        len(
            json.dumps(
                arguments, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
        )
        > INT_CUSTOM_ARGUMENT_MAX_BYTES
    ):
        raise ValueError("Custom Arguments exceed the 64 KiB JSON limit.")


class RunSettings(JsonRequest):
    max_retry_count: int = Field(default=0, ge=0, le=INT_MAX_RETRY_COUNT)
    timeout_min: int = Field(default=0, ge=0, le=INT_MAX_TIMEOUT_MIN)
    builtin_log_level: RunLogLevel = Field(default=RunLogLevel.INFO, strict=False)
    builtin_record_video: bool = False
    builtin_stop_shortcut: bool = True
    builtin_highlight_ui: bool = False
    custom_prj_args: list[list[JsonValue]] = Field(
        default_factory=list, max_length=INT_CUSTOM_ARGUMENT_MAX_COUNT
    )
    custom_arg_assets: list[OrdinaryAssetBinding | None] = Field(
        default_factory=list, max_length=INT_CUSTOM_ARGUMENT_MAX_COUNT
    )
    run_conflict_policy: RunConflictPolicy = Field(
        default=RunConflictPolicy.WAIT, strict=False
    )
    priority: RunPriority = Field(default=RunPriority.NORMAL, strict=False)
    run_email: RunEmailSettings = Field(default_factory=RunEmailSettings)

    @model_validator(mode="after")
    def validate_arguments(self) -> "RunSettings":
        for intIndex, listArgument in enumerate(self.custom_prj_args):
            if len(listArgument) != 2:
                raise ValueError(
                    f"Custom argument {intIndex + 1} must contain a name and JSON value."
                )
            argumentName = listArgument[0]
            if not isinstance(argumentName, str):
                raise ValueError(
                    f"Custom argument {intIndex + 1} must contain a name and JSON value."
                )
        validate_custom_arguments(self.custom_prj_args)
        if self.custom_arg_assets and len(self.custom_arg_assets) != len(
            self.custom_prj_args
        ):
            raise ValueError("Asset bindings must match the custom argument positions.")
        return self


class EmptyRequest(JsonRequest):
    pass


class PackageUploadRequest(JsonRequest):
    department_id: RequestUuid
    request_id: RequestUuid
    size_bytes: int = Field(gt=0, le=MAX_PACKAGE_BYTES)
    sha256: str = Field(pattern="^[0-9a-f]{64}$")


class PackageSettingsRequest(JsonRequest):
    python_environment_name: str = Field(
        min_length=1, max_length=INT_WINDOWS_NAME_MAX_LENGTH
    )
    settings: RunSettings
    api_input_keys: list[str] = Field(max_length=INT_CUSTOM_ARGUMENT_MAX_COUNT)

    @field_validator("python_environment_name")
    @classmethod
    def validate_environment_name(cls, value: str) -> str:
        validate_windows_name(value)
        return value


class PreparationResultRequest(JsonRequest):
    state: PackagePreparationResult
    reason: str = Field(default="", max_length=2000)


class PackageUploadState(TextChoices):
    RECEIVING = "receiving", "Receiving"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"
    CANCELED = "canceled", "Canceled"


class RunEmailTemplateResponse(JsonResponsePayload):
    enabled: bool
    subject: str
    body: str


class RunEmailSettingsResponse(JsonResponsePayload):
    recipient_ids: list[UUID]
    on_start: RunEmailTemplateResponse
    on_completed: RunEmailTemplateResponse
    on_error: RunEmailTemplateResponse


class RunSettingsResponse(JsonResponsePayload):
    max_retry_count: int
    timeout_min: int
    builtin_log_level: RunLogLevel
    builtin_record_video: bool
    builtin_stop_shortcut: bool
    builtin_highlight_ui: bool
    custom_prj_args: list[tuple[str, JsonValue]]
    custom_arg_assets: list[OrdinaryAssetBinding | None]
    run_conflict_policy: RunConflictPolicy
    priority: RunPriority
    run_email: RunEmailSettingsResponse


class RunEmailOutputKeysResponse(JsonResponsePayload):
    completed: list[str]
    error: list[str]


class RunSnapshotResponse(RunSettingsResponse):
    email_output_keys: RunEmailOutputKeysResponse
    package_id: UUID
    department_id: UUID
    project_name: str
    project_version: str
    sha256: str
    requires_liberrpa: str
    python_environment_name: str


class PackageListEntryResponse(JsonResponsePayload):
    id: UUID
    department_id: UUID
    department_path: str
    project_name: str
    project_version: str
    python_environment_name: str
    size_bytes: int
    uploaded_at: datetime
    uploaded_by_name: str
    can_manage: bool


class PackageResponse(PackageListEntryResponse):
    description: str
    version_summary: str
    requires_liberrpa: str
    component_dependencies: dict[str, JsonValue]
    sha256: str
    settings: RunSettingsResponse
    api_input_keys: list[str]


class PackageReferenceResponse(JsonResponsePayload):
    id: UUID
    name: str
    kind: PackageReferenceKind


class PackagePreparationResponse(JsonResponsePayload):
    executor_id: UUID
    executor_name: str
    state: PackagePreparationState
    reason: str
    from_previous_association: bool


class PackageDetailsResponse(JsonResponsePayload):
    package: PackageResponse
    preparation: list[PackagePreparationResponse]
    references: list[PackageReferenceResponse]


class PackageProjectGroupResponse(JsonResponsePayload):
    department_id: UUID
    department_path: str
    project_name: str
    project_name_key: str


class PackageProjectGroupEntryResponse(PackageProjectGroupResponse):
    latest_package_id: UUID


class PackageProjectGroupListResponse(PaginationResponse):
    project_groups: list[PackageProjectGroupEntryResponse]


class ProjectPackageEntryResponse(JsonResponsePayload):
    id: UUID
    project_version: str


class ProjectPackageListResponse(PaginationResponse):
    project_group: PackageProjectGroupResponse
    packages: list[ProjectPackageEntryResponse]


class PackageOptionEntryResponse(PackageListEntryResponse):
    project_name_key: str


class PackageOptionsResponse(JsonResponsePayload):
    packages: list[PackageOptionEntryResponse]


class PackageUploadResponse(JsonResponsePayload):
    upload_id: UUID
    state: PackageUploadState
    offset: int
    size_bytes: int
    chunk_bytes: int
    expires_at: datetime
    package: PackageResponse | None


class PackagePreparationCancellationResponse(JsonResponsePayload):
    canceled_count: int


class PackageDownloadResponse(JsonResponsePayload):
    transfer_id: UUID
    file_name: str
