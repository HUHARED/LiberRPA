# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field

from console_project.contracts import JsonResponsePayload, PaginationResponse


class AuditChannel(TextChoices):
    SESSION = "session", "Web"
    EDITOR = "editor", "Editor"
    EXECUTOR = "executor", "Executor"
    API_KEY = "api_key", "API Key"
    SYSTEM = "system", "System"


class AuditResult(TextChoices):
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class AuditStage(TextChoices):
    OPERATION = "operation", "Operation"
    REQUEST = "request", "Request"


class AuditRecordResponse(JsonResponsePayload):
    id: UUID
    created_at: datetime
    actor_id: UUID | None
    actor_name: str
    channel: AuditChannel = Field(strict=False)
    module: str
    action: str
    object_type: str
    object_id: str
    object_name: str
    result: AuditResult = Field(strict=False)


class AuditListResponse(JsonResponsePayload):
    records: list[AuditRecordResponse]
    pagination: PaginationResponse


class AuditActorResponse(JsonResponsePayload):
    id: UUID | None
    name: str


class AuditFilterOptionsResponse(JsonResponsePayload):
    actors: list[AuditActorResponse]
    modules: list[str]
    actions: list[str]


class AuditChangeResponse(JsonResponsePayload):
    field: str
    # Null means the value was not recorded; a recorded JSON null is the text "null".
    before: str | None
    after: str | None


class AuditDetailsRecordResponse(AuditRecordResponse):
    organization_id: UUID
    organization_name: str
    department_id: UUID | None
    request_id: UUID | None
    stage: AuditStage = Field(strict=False)
    reason_code: str | None
    http_status: int | None
    changes: list[AuditChangeResponse]
    details_omitted: bool


class AuditDetailsResponse(JsonResponsePayload):
    record: AuditDetailsRecordResponse
