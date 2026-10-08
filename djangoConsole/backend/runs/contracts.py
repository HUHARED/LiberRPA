# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from pydantic import (
    AwareDatetime,
    Field,
    JsonValue,
    ModelWrapValidatorHandler,
    model_validator,
)

from console_project.contracts import JsonRequest
from console_project.validators import validate_json_text, validate_json_value
from packages.contracts import INT_CUSTOM_ARGUMENT_MAX_BYTES

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


class RunOutputs(JsonRequest):
    status: Annotated[OutputsStatus, Field(strict=False)] = OutputsStatus.UNAVAILABLE
    values: list[Annotated[tuple[str, JsonValue], Field(strict=False)]] | None = None
    unavailable_keys: list[str] = Field(default_factory=list, alias="unavailableKeys")
    reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        validate_json_text(self.reason)
        if self.status == OutputsStatus.UNAVAILABLE:
            if self.values is not None or self.unavailable_keys:
                raise ValueError("Unavailable outputs cannot contain values or keys.")
            return self
        if (
            self.status not in (OutputsStatus.COMPLETE, OutputsStatus.PARTIAL)
            or self.values is None
            or (self.status == OutputsStatus.PARTIAL) != bool(self.unavailable_keys)
        ):
            raise ValueError("Run outputs do not match their status.")
        setKey = set(self.unavailable_keys)
        if len(setKey) != len(self.unavailable_keys):
            raise ValueError("Run unavailable keys contain duplicates.")
        for strKey, _value in self.values:
            if strKey in setKey:
                raise ValueError("Run output keys must be unique.")
            setKey.add(strKey)
        # Validate JSON arrays rather than Python tuples so depth matches input pairs.
        listValue = [[strKey, value] for strKey, value in self.values]
        for value in (listValue, self.unavailable_keys):
            validate_json_value(cast(JsonValue, value))
            if (
                len(
                    json.dumps(
                        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                    ).encode("utf-8")
                )
                > INT_CUSTOM_ARGUMENT_MAX_BYTES
            ):
                raise ValueError(
                    "Run output values or keys exceed the 64 KiB JSON limit."
                )
        return self

    @model_validator(mode="wrap")
    @classmethod
    def parse_snapshot(
        cls, value: object, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        try:
            return handler(value)
        except (ValueError, UnicodeError, RecursionError):
            # Output diagnostics degrade without relaxing event identity or time checks.
            return cls.model_construct(
                status=OutputsStatus.UNAVAILABLE,
                values=None,
                unavailable_keys=[],
                reason="The output snapshot was invalid or exceeded the shared JSON limits.",
            )


class WorkEvent(JsonRequest):
    event_id: UuidValue
    assignment_id: UuidValue
    kind: Annotated[RunEventKind, Field(strict=False)]
    occurred_at: Annotated[AwareDatetime, Field(strict=False)]
    started_at: Annotated[AwareDatetime, Field(strict=False)] | None = None
    result: Annotated[RunResult, Field(strict=False)] | None = None
    outputs: RunOutputs = Field(default_factory=RunOutputs)
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
