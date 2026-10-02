# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Literal
from uuid import UUID

from console_project.contracts import JsonResponsePayload
from organizations.contracts import PaginationResponse


class AuditRecordResponse(JsonResponsePayload):
    id: UUID
    created_at: datetime
    actor_id: UUID | None
    actor_name: str
    channel: Literal["session", "editor", "executor", "api_key", "system"]
    module: str
    action: str
    object_type: str
    object_id: str
    object_name: str
    result: Literal["succeeded", "failed"]


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
    stage: Literal["operation", "request"]
    reason_code: str | None
    http_status: int | None
    changes: list[AuditChangeResponse]
    details_omitted: bool


class AuditDetailsResponse(JsonResponsePayload):
    record: AuditDetailsRecordResponse
