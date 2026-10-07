# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from console_project.contracts import JsonRequest

from .models import RunEventKind, RunResult, OutputsStatus, RecordingStatus

UuidValue = Annotated[uuid.UUID, Field(strict=False)]


class JobCreationRequest(JsonRequest):
    request_id: UuidValue
    package_id: UuidValue
    # Creation quotas do not limit the use of existing Executors; services validate target membership.
    executor_ids: list[UuidValue] = Field(default_factory=list)
    group_id: UuidValue | None = None
    settings: dict[str, JsonValue] | None = None
    custom_args: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_targets(self) -> "JobCreationRequest":
        if bool(self.executor_ids) == (self.group_id is not None):
            raise ValueError("Select Executors or one group.")
        if len(set(self.executor_ids)) != len(self.executor_ids):
            raise ValueError("Select each Executor only once.")
        return self


class JobControlRequest(JsonRequest):
    action: Literal["cancel", "stop", "close"]


class EmptyRequest(JsonRequest):
    pass


class WorkPollRequest(JsonRequest):
    running_run_ids: list[UuidValue] = Field(default_factory=list, max_length=500)
    local_waiting_count: int = Field(ge=0, le=10000)
    local_running_count: int = Field(default=0, ge=0, le=10000)


class WorkPermitRequest(JsonRequest):
    assignment_id: UuidValue


class RecordingInfo(JsonRequest):
    status: Annotated[RecordingStatus, Field(strict=False)]
    videoSizeBytes: int | None = Field(default=None, ge=0)
    subtitleSizeBytes: int | None = Field(default=None, ge=0)
    reason: str = Field(default="", max_length=2000)


class RunNotStartedReason(StrEnum):
    LOCAL_CONFLICT = "local_conflict"


class WorkEvent(JsonRequest):
    event_id: UuidValue
    assignment_id: UuidValue
    kind: Annotated[RunEventKind, Field(strict=False)]
    occurred_at: Annotated[AwareDatetime, Field(strict=False)]
    started_at: Annotated[AwareDatetime, Field(strict=False)] | None = None
    result: Annotated[RunResult, Field(strict=False)] | None = None
    outputs_status: Annotated[OutputsStatus, Field(strict=False)] = (
        OutputsStatus.UNAVAILABLE
    )
    outputs: dict[str, JsonValue] | None = None
    outputs_reason: str = Field(default="", max_length=2000)
    outputs_unavailable_keys: list[str] = Field(default_factory=list)
    error_summary: dict[str, str] | None = None
    recording: RecordingInfo | None = None
    reason: str = Field(default="", max_length=2000)
    not_started_reason: Annotated[RunNotStartedReason, Field(strict=False)] | None = None

    @model_validator(mode="after")
    def validate_event(self) -> "WorkEvent":
        if self.not_started_reason is not None and self.kind != RunEventKind.NOT_STARTED:
            raise ValueError("A non-start reason requires a not_started event.")
        if self.kind == RunEventKind.ENDED:
            if self.started_at is None or self.result in (None, RunResult.RUNNING):
                raise ValueError(
                    "An ended event requires actual start time and a final result."
                )
            if self.occurred_at < self.started_at:
                raise ValueError("The end time precedes the start time.")
        return self


class WorkEventsRequest(JsonRequest):
    events: list[WorkEvent] = Field(min_length=1, max_length=50)
