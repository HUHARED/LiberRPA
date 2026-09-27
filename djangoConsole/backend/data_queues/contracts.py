# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from console_project.contracts import JsonRequest, JsonResponsePayload, JsonValue

type QueueUuid = Annotated[UUID, Field(strict=False)]
type QueueStatus = Literal["unclaimed", "claimed"]
type QueueFilterStatus = Literal["all", "unclaimed", "claimed"]
type QueueOrder = Literal["oldest_first", "newest_first"]
type QueueItemIds = Annotated[list[QueueUuid], Field(min_length=1, max_length=100)]


class QueueDetailsRequest(JsonRequest):
    name: str
    notes: str = ""


class QueueCreationRequest(QueueDetailsRequest):
    department_id: QueueUuid


class QueueDeletionRequest(JsonRequest):
    pass


class QueueMutationRequest(JsonRequest):
    request_id: QueueUuid
    queue_path: str | None = Field(default=None, max_length=1024)


class QueueUploadRequest(QueueMutationRequest):
    items: list[JsonValue] = Field(min_length=1, max_length=100)


class QueueSelectionRequest(JsonRequest):
    status: QueueFilterStatus = "all"
    order: QueueOrder = "oldest_first"
    item_id: QueueUuid | None = None
    count: int = Field(default=50, ge=1, le=100)


class QueueQueryRequest(QueueSelectionRequest):
    queue_path: str = Field(max_length=1024)
    after_sequence: int | None = Field(default=None, ge=0)


class QueueClaimRequest(QueueMutationRequest, QueueSelectionRequest):
    status: QueueFilterStatus = "unclaimed"
    count: int = Field(default=1, ge=1, le=100)


class QueueResetRequest(QueueMutationRequest):
    item_ids: QueueItemIds


class QueueDeleteItemsRequest(QueueMutationRequest):
    item_ids: QueueItemIds | None = None
    status: QueueFilterStatus = "claimed"
    order: QueueOrder = "oldest_first"
    count: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.item_ids is not None and self.model_fields_set & {
            "status",
            "order",
            "count",
        }:
            raise ValueError("Choose item_ids or status/count/order, not both.")
        return self


class QueueDepartmentResponse(JsonResponsePayload):
    id: UUID
    path: str


class QueueEntryResponse(JsonResponsePayload):
    id: UUID
    name: str
    department: QueueDepartmentResponse
    path: str
    notes: str
    unclaimed_count: int
    claimed_count: int
    can_manage: bool
    created_at: datetime
    updated_at: datetime


class QueueDetailsResponse(JsonResponsePayload):
    queue: QueueEntryResponse


class QueuePageResponse(JsonResponsePayload):
    page: int
    page_size: int
    total_count: int
    total_pages: int


class QueueListResponse(QueuePageResponse):
    queues: list[QueueEntryResponse]


class QueueItemResponse(JsonResponsePayload):
    id: UUID
    sequence: int
    status: QueueStatus
    data_summary: str
    uploaded_by_id: UUID
    uploaded_by_name: str
    uploaded_at: datetime
    last_claimed_by_id: UUID | None
    last_claimed_by_name: str
    last_claimed_at: datetime | None


class QueueItemDetailsResponse(QueueItemResponse):
    data: JsonValue


class QueueItemsResponse(QueuePageResponse):
    queue: QueueEntryResponse
    items: list[QueueItemResponse]


class QueueClaimedItemResponse(JsonResponsePayload):
    id: UUID
    data: JsonValue


class QueueMutationResponse(JsonResponsePayload):
    request_id: UUID
    accepted_at: datetime
    item_ids: list[UUID]
    missing_ids: list[UUID]
    skipped_ids: list[UUID]
    items: list[QueueClaimedItemResponse]
    deduplicated: bool


class QueueQueryResponse(JsonResponsePayload):
    items: list[QueueItemDetailsResponse]
    next_sequence: int | None
