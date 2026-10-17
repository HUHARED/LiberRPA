# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from django.db.models import TextChoices
from pydantic import (
    AwareDatetime,
    Field,
    ModelWrapValidatorHandler,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_validator,
)

from console_project.contracts import JsonValue, JsonRequest, JsonResponsePayload
from console_project.constants import RunLogLevel
from console_project.validators import validate_json_string, validate_json_value
from organizations.contracts import PaginationResponse
from notifications.contracts import (
    INT_RUN_EMAIL_MAX_BYTES,
    RunEmailOutputValue,
)
from packages.contracts import (
    INT_CUSTOM_ARGUMENT_MAX_BYTES,
    RunPriority,
    RunSnapshotResponse,
)


class JobSource(TextChoices):
    MANUAL = "manual", "Manual"
    API = "api", "API"
    SCHEDULE = "schedule", "Schedule"


class JobState(TextChoices):
    WAITING = "waiting", "Waiting"
    PREPARING = "preparing", "Preparing"
    STARTING = "starting", "Starting"
    RUNNING = "running", "Running"
    STOPPING = "stopping", "Stopping"
    WAITING_RETRY = "waiting_retry", "Waiting for Retry"
    NEEDS_REVIEW = "needs_review", "Needs Review"
    FINISHED = "finished", "Finished"


class AssignmentState(TextChoices):
    PREPARING = "preparing", "Preparing"
    PERMITTED = "permitted", "Permitted"
    RUNNING = "running", "Running"
    NEEDS_REVIEW = "needs_review", "Needs Review"
    FINISHED = "finished", "Finished"
    WITHDRAWN = "withdrawn", "Withdrawn"


ACTIVE_ASSIGNMENT_STATES = (
    AssignmentState.PREPARING,
    AssignmentState.PERMITTED,
    AssignmentState.RUNNING,
    AssignmentState.NEEDS_REVIEW,
)


class RunStatus(TextChoices):
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    ERROR = "error", "Error"
    CANCELED = "canceled", "Canceled"
    TIMED_OUT = "timed_out", "Timed Out"
    INTERRUPTED = "interrupted", "Interrupted"


type RunEndedStatus = Literal[
    RunStatus.COMPLETED,
    RunStatus.ERROR,
    RunStatus.CANCELED,
    RunStatus.TIMED_OUT,
    RunStatus.INTERRUPTED,
]


class OutputsStatus(TextChoices):
    WAITING = "waiting", "Waiting"
    COMPLETE = "complete", "Complete"
    PARTIAL = "partial", "Partial"
    UNAVAILABLE = "unavailable", "Unavailable"


class RecordingStatus(TextChoices):
    RECORDING = "recording", "Recording"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    UNAVAILABLE = "unavailable", "Unavailable"


class RunEventKind(TextChoices):
    STARTED = "started", "Started"
    ENDED = "ended", "Ended"
    PREPARATION_FAILED = "preparation_failed", "Preparation Failed"
    NOT_STARTED = "not_started", "Not Started"
    UNKNOWN = "unknown", "Unknown"
    RECORDING = "recording", "Recording"


class RunFileKind(TextChoices):
    LOGS = "logs", "Logs"
    VIDEO = "video", "Video"
    SUBTITLES = "subtitles", "Subtitles"


class JobControlAction(TextChoices):
    CANCEL = "cancel", "Cancel"
    STOP = "stop", "Stop"
    CLOSE = "close", "Close"


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
    action: Annotated[JobControlAction, Field(strict=False)]


class ClearLogsRequest(JsonRequest):
    run_ids: list[Annotated[uuid.UUID, Field(strict=False)]] = Field(
        min_length=1, max_length=20000
    )


class RunFileRequest(JsonRequest):
    kind: Annotated[RunFileKind, Field(strict=False)]


class EmptyRequest(JsonRequest):
    pass


class WorkPollRequest(JsonRequest):
    running_run_ids: list[UuidValue] = Field(default_factory=list, max_length=500)
    local_waiting_count: int = Field(ge=0, le=10000)
    other_active_run_count: int = Field(default=0, ge=0, le=10000)


class WorkEventRetentionRequest(JsonRequest):
    assignment_ids: list[UuidValue] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_assignments(self) -> Self:
        if len(set(self.assignment_ids)) != len(self.assignment_ids):
            raise ValueError("Include each assignment only once.")
        return self


class WorkPermitRequest(JsonRequest):
    assignment_id: UuidValue


class RunNotStartedReason(StrEnum):
    LOCAL_CONFLICT = "local_conflict"


class RecordingInfo(JsonRequest):
    status: Annotated[RecordingStatus, Field(strict=False)]
    videoSizeBytes: int | None = Field(default=None, ge=0)
    subtitleSizeBytes: int | None = Field(default=None, ge=0)
    reason: str = Field(default="", max_length=2000)


class RunOutputs(JsonRequest):
    status: Annotated[OutputsStatus, Field(strict=False)] = OutputsStatus.UNAVAILABLE
    values: list[Annotated[tuple[str, JsonValue], Field(strict=False)]] | None = None
    unavailable_keys: list[str] = Field(default_factory=list, alias="unavailableKeys")
    reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        validate_json_string(self.reason)
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
            # Invalid Outputs are reported as unavailable; event identity and time checks still apply.
            return cls.model_construct(
                status=OutputsStatus.UNAVAILABLE,
                values=None,
                unavailable_keys=[],
                reason="The output snapshot was invalid or exceeded the shared JSON limits.",
            )


class WorkEventBase(JsonRequest):
    event_id: UuidValue
    assignment_id: UuidValue
    occurred_at: Annotated[AwareDatetime, Field(strict=False)]
    reason: str = Field(default="", max_length=2000)


class WorkStartedEvent(WorkEventBase):
    kind: Literal[RunEventKind.STARTED]
    started_at: Annotated[AwareDatetime, Field(strict=False)]


class WorkEndedEvent(WorkEventBase):
    kind: Literal[RunEventKind.ENDED]
    started_at: Annotated[AwareDatetime, Field(strict=False)]
    status: RunEndedStatus
    outputs: RunOutputs = Field(default_factory=RunOutputs)
    email_output_context: list[RunEmailOutputValue] | None = None
    error_summary: dict[str, str] | None = None

    @field_validator("email_output_context", mode="wrap")
    @classmethod
    def parse_email_output_context(
        cls, value: object, handler: ValidatorFunctionWrapHandler
    ) -> list[RunEmailOutputValue] | None:
        try:
            context: list[RunEmailOutputValue] | None = handler(value)
            if context is not None and (
                len({entry.key for entry in context}) != len(context)
                or sum(len(entry.text.encode("utf-8")) for entry in context)
                > INT_RUN_EMAIL_MAX_BYTES
            ):
                raise ValueError("The email output context exceeds its limits.")
            return context
        except (ValueError, UnicodeError, RecursionError):
            # Email capture cannot invalidate an otherwise valid execution result.
            return None

    @model_validator(mode="after")
    def validate_times(self) -> Self:
        if self.occurred_at < self.started_at:
            raise ValueError("The end time precedes the start time.")
        return self


class WorkPreparationFailedEvent(WorkEventBase):
    kind: Literal[RunEventKind.PREPARATION_FAILED]


class WorkNotStartedEvent(WorkEventBase):
    kind: Literal[RunEventKind.NOT_STARTED]
    not_started_reason: Annotated[RunNotStartedReason, Field(strict=False)] | None = None


class WorkUnknownEvent(WorkEventBase):
    kind: Literal[RunEventKind.UNKNOWN]


class WorkRecordingEvent(WorkEventBase):
    kind: Literal[RunEventKind.RECORDING]
    recording: RecordingInfo


type WorkEvent = Annotated[
    WorkStartedEvent
    | WorkEndedEvent
    | WorkPreparationFailedEvent
    | WorkNotStartedEvent
    | WorkUnknownEvent
    | WorkRecordingEvent,
    Field(discriminator="kind"),
]


class WorkEventsRequest(JsonRequest):
    events: list[WorkEvent] = Field(min_length=1, max_length=50)


class JobResponse(JsonResponsePayload):
    id: uuid.UUID
    job_request_id: uuid.UUID
    department_id: uuid.UUID
    source: JobSource
    schedule_id: uuid.UUID | None
    schedule_name: str
    scheduled_at: datetime | None
    project_name: str
    project_version: str
    package_id: uuid.UUID | None
    target_type: Literal["executor", "group"]
    target_id: uuid.UUID
    target_name: str
    executor_id: uuid.UUID | None
    executor_name: str | None
    priority: RunPriority
    state: JobState
    reason: str
    queued_at: datetime
    retry_at: datetime | None
    closed_at: datetime | None
    ended_at: datetime | None
    can_cancel: bool
    can_stop: bool
    can_close: bool


class JobEventResponse(JsonResponsePayload):
    kind: RunEventKind
    occurred_at: datetime
    reason: str


class RunResponse(JsonResponsePayload):
    id: uuid.UUID
    job_id: uuid.UUID
    department_id: uuid.UUID
    schedule_name: str
    project_name: str
    project_version: str
    executor_id: uuid.UUID
    executor_name: str
    account_name: str
    computer_name: str
    attempt_number: int
    started_at: datetime
    ended_at: datetime | None
    status: RunStatus
    reason: str
    outputs_status: OutputsStatus
    can_rerun: bool
    can_stop: bool


class JobDetailsEntryResponse(JobResponse):
    run_snapshot: RunSnapshotResponse
    runs: list[RunResponse]
    events: list[JobEventResponse]


class JobDetailsResponse(JsonResponsePayload):
    job: JobDetailsEntryResponse


class JobListResponse(PaginationResponse):
    jobs: list[JobResponse]


class JobCreationResponse(JsonResponsePayload):
    request_id: uuid.UUID
    job_request_id: uuid.UUID
    jobs: list[JobResponse]


class RunFileAvailabilityResponse(JsonResponsePayload):
    available: bool
    reason: str
    size_bytes: int | None


class RunFilesResponse(JsonResponsePayload):
    logs: RunFileAvailabilityResponse
    video: RunFileAvailabilityResponse
    subtitles: RunFileAvailabilityResponse


class RunRecordingResponse(JsonResponsePayload):
    status: RecordingStatus | None = None
    reason: str = ""
    videoSizeBytes: int | None = None
    subtitleSizeBytes: int | None = None


class RunDetailsEntryResponse(RunResponse):
    department_path: str
    department_deleted_at: datetime | None
    run_snapshot: RunSnapshotResponse
    outputs: list[tuple[str, JsonValue]] | None
    outputs_reason: str
    outputs_unavailable_keys: list[str]
    error_summary: dict[str, JsonValue] | None
    job: JobResponse
    other_runs: list[RunResponse]
    logs_cleared_at: datetime | None
    recording: RunRecordingResponse
    files: RunFilesResponse


class RunDetailsResponse(JsonResponsePayload):
    run: RunDetailsEntryResponse


class RunListResponse(PaginationResponse):
    runs: list[RunResponse]


class RunSelectionResponse(JsonResponsePayload):
    run_ids: list[uuid.UUID]


class RunRerunResponse(JsonResponsePayload):
    package_id: uuid.UUID
    executor_ids: list[uuid.UUID]
    group_id: uuid.UUID | None
    original_job_active: bool


class RunLogEntryResponse(JsonResponsePayload):
    log_id: uuid.UUID
    sequence: int
    timestamp: datetime
    received_at: datetime
    level: RunLogLevel
    user_name: str
    machine_name: str
    process_name: str
    file_name: str
    line_no: str
    project_name: str
    message_text: str
    message_omitted: bool
    custom_fields: dict[str, str]


class RunLogListResponse(JsonResponsePayload):
    logs: list[RunLogEntryResponse]
    before_cursor: int | None
    after_cursor: int
    has_more: bool
    cleared: bool
    complete: bool
    unavailable_reason: str


class RunLogClearEntryResponse(JsonResponsePayload):
    id: uuid.UUID
    reason: str


class RunLogClearResponse(JsonResponsePayload):
    cleared: int
    skipped: list[RunLogClearEntryResponse]
    failed: list[RunLogClearEntryResponse]


class RunDownloadResponse(JsonResponsePayload):
    download_url: str


class RunDepartmentResponse(JsonResponsePayload):
    id: uuid.UUID
    name: str
    path: str
    deleted_at: datetime | None


class RunDepartmentListResponse(JsonResponsePayload):
    departments: list[RunDepartmentResponse]
