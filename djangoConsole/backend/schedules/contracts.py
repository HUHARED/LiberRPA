# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from console_project.contracts import JsonRequest, JsonResponsePayload
from organizations.contracts import PaginationResponse
from packages.contracts import RunConflictPolicy, RunSettings, RunSettingsResponse

UuidValue = Annotated[UUID, Field(strict=False)]


class ScheduleTimeRequest(JsonRequest):
    cron: str = Field(min_length=1, max_length=200)
    time_zone: str = Field(min_length=1, max_length=100)
    active_from: str = Field(min_length=1, max_length=50)
    active_until: str = Field(min_length=1, max_length=50)


class ScheduleSaveRequest(ScheduleTimeRequest):
    department_id: UuidValue
    name: str = Field(min_length=1, max_length=128)
    notes: str = Field(default="", max_length=2000)
    package_id: UuidValue
    # Creation quotas do not limit the use of existing Executors; services validate target membership.
    executor_ids: list[UuidValue] = Field(default_factory=list)
    group_id: UuidValue | None = None
    enabled: bool = True
    settings: RunSettings


class ScheduleEnabledRequest(JsonRequest):
    enabled: bool


class ScheduleDeletionRequest(JsonRequest):
    pass


class ScheduleNamedObjectResponse(JsonResponsePayload):
    id: UUID
    name: str


class ScheduleDepartmentResponse(ScheduleNamedObjectResponse):
    path: str


class ScheduleCreatorResponse(JsonResponsePayload):
    id: UUID
    username: str
    email: str


class ScheduleListEntryResponse(JsonResponsePayload):
    id: UUID
    name: str
    department_id: UUID
    department: ScheduleDepartmentResponse
    package_id: UUID
    project_name: str
    project_version: str
    executor_ids: list[UUID]
    executors: list[ScheduleNamedObjectResponse]
    group_id: UUID | None
    executor_group: ScheduleNamedObjectResponse | None
    enabled: bool
    notes: str
    cron: str
    run_conflict_policy: RunConflictPolicy
    time_zone: str
    active_from: datetime
    active_until: datetime
    created_at: datetime
    created_by: ScheduleCreatorResponse | None
    can_manage: bool


class ScheduleResponse(ScheduleListEntryResponse):
    settings: RunSettingsResponse
    python_environment_name: str
    upcoming_triggers: list[datetime]


class ScheduleListResponse(PaginationResponse):
    schedules: list[ScheduleListEntryResponse]


class ScheduleDetailsResponse(JsonResponsePayload):
    schedule: ScheduleResponse


class ScheduleDefaultsResponse(JsonResponsePayload):
    time_zone: str


class SchedulePreviewResponse(JsonResponsePayload):
    normalized_cron: str
    upcoming_triggers: list[datetime]
