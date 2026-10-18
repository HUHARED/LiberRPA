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

from console_project.contracts import (
    JsonValue,
    JsonRequest,
    JsonResponsePayload,
    PaginationResponse,
)

MAX_QUEUE_RESPONSE_BYTES = 2 * 1024 * 1024

type QueueRequestUuid = Annotated[UUID, Field(strict=False)]
type QueueItemIds = Annotated[list[QueueRequestUuid], Field(min_length=1, max_length=100)]


class QueueItemStatus(StrEnum):
    UNCLAIMED = "unclaimed"
    CLAIMED = "claimed"


class QueueItemFilterStatus(StrEnum):
    ALL = "all"
    UNCLAIMED = QueueItemStatus.UNCLAIMED
    CLAIMED = QueueItemStatus.CLAIMED


class QueueItemOrder(StrEnum):
    OLDEST_FIRST = "oldest_first"
    NEWEST_FIRST = "newest_first"


class QueueDetailsRequest(JsonRequest):
    name: str
    notes: str = ""


class QueueCreationRequest(QueueDetailsRequest):
    department_id: QueueRequestUuid


class QueueDeletionRequest(JsonRequest):
    pass


class QueueMutationRequest(JsonRequest):
    request_id: QueueRequestUuid
    queue_path: str | None = Field(default=None, min_length=1, max_length=16384)


class QueueUploadRequest(QueueMutationRequest):
    items: list[JsonValue] = Field(min_length=1, max_length=100)


class QueueSelectionRequest(JsonRequest):
    status: QueueItemFilterStatus = Field(default=QueueItemFilterStatus.ALL, strict=False)
    order: QueueItemOrder = Field(default=QueueItemOrder.OLDEST_FIRST, strict=False)
    item_id: QueueRequestUuid | None = None
    count: int = Field(default=50, ge=1, le=100)


class QueueQueryRequest(QueueSelectionRequest):
    queue_path: str = Field(min_length=1, max_length=16384)
    after_sequence: int | None = Field(default=None, ge=0)


class QueueClaimRequest(QueueMutationRequest, QueueSelectionRequest):
    status: QueueItemFilterStatus = Field(
        default=QueueItemFilterStatus.UNCLAIMED, strict=False
    )
    count: int = Field(default=1, ge=1, le=100)


class QueueResetRequest(QueueMutationRequest):
    item_ids: QueueItemIds


class QueueDeleteItemsRequest(QueueMutationRequest):
    item_ids: QueueItemIds | None = None
    status: QueueItemFilterStatus = Field(
        default=QueueItemFilterStatus.CLAIMED, strict=False
    )
    order: QueueItemOrder = Field(default=QueueItemOrder.OLDEST_FIRST, strict=False)
    count: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.item_ids is not None and self.model_fields_set & {
            "status",
            "order",
            "count",
        }:
            raise ValueError("Choose item_ids or status/count/order, not both.")
        if self.item_ids is None and not {"status", "count"} <= self.model_fields_set:
            raise ValueError("Specify status and count when deleting without item_ids.")
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


class QueueListResponse(PaginationResponse):
    queues: list[QueueEntryResponse]


class QueueItemResponse(JsonResponsePayload):
    id: UUID
    sequence: int
    status: QueueItemStatus = Field(strict=False)
    data_summary: str
    uploaded_by_id: UUID
    uploaded_by_name: str
    uploaded_at: datetime
    last_claimed_by_id: UUID | None
    last_claimed_by_name: str
    last_claimed_at: datetime | None


class QueueItemDetailsResponse(QueueItemResponse):
    data: JsonValue


class QueueItemsResponse(PaginationResponse):
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
    next_after_sequence: int | None
