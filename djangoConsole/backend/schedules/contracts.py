# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import Annotated
from uuid import UUID

from pydantic import Field

from console_project.contracts import JsonRequest
from packages.contracts import RunSettings

UuidValue = Annotated[UUID, Field(strict=False)]


class ScheduleTimeRequest(JsonRequest):
    cron: str = Field(min_length=1, max_length=200)
    time_zone: str = Field(min_length=1, max_length=100)
    active_from: str = Field(min_length=1, max_length=50)
    active_until: str = Field(min_length=1, max_length=50)


class ScheduleUpdateRequest(ScheduleTimeRequest):
    name: str = Field(min_length=1, max_length=128)
    notes: str = Field(default="", max_length=2000)
    package_id: UuidValue
    # Creation quotas do not limit the use of existing Executors; services validate target membership.
    executor_ids: list[UuidValue] = Field(default_factory=list)
    group_id: UuidValue | None = None
    enabled: bool = True
    settings: RunSettings


class ScheduleCreationRequest(ScheduleUpdateRequest):
    department_id: UuidValue


class ScheduleEnabledRequest(JsonRequest):
    enabled: bool


class ScheduleDeletionRequest(JsonRequest):
    pass
