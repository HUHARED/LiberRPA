# FileName: limits.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from pydantic import ValidationError as PydanticValidationError

from console_project.config import LimitsConfig

if TYPE_CHECKING:
    from .models import Organization


class OrganizationLimit(models.TextChoices):
    MEMBERS = "maxMembersPerOrganization", "Members"
    DEPARTMENTS = "maxDepartmentsPerOrganization", "Departments"
    EXECUTORS = "maxExecutorsPerOrganization", "Executors"
    EXECUTOR_GROUPS = "maxExecutorGroupsPerOrganization", "Executor Groups"
    PROJECTS = "maxProjectsPerOrganization", "Projects"
    PACKAGES_PER_PROJECT = "maxPackagesPerProject", "Packages per Project"
    SCHEDULES = "maxSchedulesPerOrganization", "Schedules"
    ASSETS = "maxAssetsPerOrganization", "Assets"
    DATA_QUEUES = "maxDataQueuesPerOrganization", "Data Queues"
    SHARED_FILES = "maxSharedFilesPerOrganization", "Shared Files"
    RUN_EMAIL_ADDRESSES = (
        "maxRunEmailAddressesPerOrganization",
        "Additional Run Email Addresses",
    )
    STORED_BYTES = "maxStoredBytesPerOrganization", "Package and Shared File Storage"
    QUEUE_ITEMS = "maxQueueItemsPerOrganization", "Queue Items"
    QUEUE_DATA_BYTES = "maxQueueDataBytesPerOrganization", "Queue Data"
    RUN_LOG_BYTES = "maxRunLogBytesPerOrganization", "Run Log Storage"
    RUN_LOG_GROUPS = "maxRunLogGroupsPerOrganization", "Run Log Groups"
    RUN_HISTORY = "maxRunHistoryPerOrganization", "Run History"
    ACTIVE_JOBS = "maxActiveJobsPerOrganization", "Active Jobs"
    NEW_JOBS_PER_MINUTE = "newJobsPerMinute", "New Jobs per Minute"
    NEW_JOBS_BURST = "newJobsBurst", "New Job Burst"
    READ_REQUESTS_PER_MINUTE = (
        "organizationReadRequestsPerMinute",
        "Read Requests per Minute",
    )
    WRITE_OBJECTS_PER_MINUTE = (
        "organizationWriteObjectsPerMinute",
        "Write Operations per Minute",
    )
    ACTIVE_UPLOADS = "maxActiveUploadsPerOrganization", "Concurrent Uploads"
    ACTIVE_DOWNLOADS = "maxActiveDownloadsPerOrganization", "Concurrent Downloads"


class LimitUnit(models.TextChoices):
    COUNT = "count", "Count"
    BYTES = "bytes", "Bytes"
    PER_MINUTE = "per_minute", "Per Minute"


# LimitInteger is a named type alias, so each field refers to its range in $defs.
_DICT_CONFIG_SCHEMA = LimitsConfig.model_json_schema()
_DICT_LIMIT_SCHEMA = {
    strConfigName: _DICT_CONFIG_SCHEMA["$defs"][
        dictFieldSchema["$ref"].removeprefix("#/$defs/")
    ]
    for strConfigName, dictFieldSchema in _DICT_CONFIG_SCHEMA["properties"].items()
}


@dataclass(frozen=True)
class OrganizationLimitDefinition:
    key: OrganizationLimit
    unit: LimitUnit

    @property
    def configName(self) -> str:
        return self.key.value

    @property
    def label(self) -> str:
        return str(self.key.label)

    @property
    def minimum(self) -> int:
        return _DICT_LIMIT_SCHEMA[self.configName]["minimum"]

    @property
    def maximum(self) -> int | None:
        return _DICT_LIMIT_SCHEMA[self.configName].get("maximum")


LIMIT_DEFINITIONS = (
    OrganizationLimitDefinition(OrganizationLimit.MEMBERS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.DEPARTMENTS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.EXECUTORS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.EXECUTOR_GROUPS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.PROJECTS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.PACKAGES_PER_PROJECT, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.SCHEDULES, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.ASSETS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.DATA_QUEUES, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.SHARED_FILES, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.RUN_EMAIL_ADDRESSES, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.STORED_BYTES, LimitUnit.BYTES),
    OrganizationLimitDefinition(OrganizationLimit.QUEUE_ITEMS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.QUEUE_DATA_BYTES, LimitUnit.BYTES),
    OrganizationLimitDefinition(OrganizationLimit.RUN_LOG_BYTES, LimitUnit.BYTES),
    OrganizationLimitDefinition(OrganizationLimit.RUN_LOG_GROUPS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.RUN_HISTORY, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.ACTIVE_JOBS, LimitUnit.COUNT),
    OrganizationLimitDefinition(
        OrganizationLimit.NEW_JOBS_PER_MINUTE, LimitUnit.PER_MINUTE
    ),
    OrganizationLimitDefinition(OrganizationLimit.NEW_JOBS_BURST, LimitUnit.COUNT),
    OrganizationLimitDefinition(
        OrganizationLimit.READ_REQUESTS_PER_MINUTE, LimitUnit.PER_MINUTE
    ),
    OrganizationLimitDefinition(
        OrganizationLimit.WRITE_OBJECTS_PER_MINUTE, LimitUnit.PER_MINUTE
    ),
    OrganizationLimitDefinition(OrganizationLimit.ACTIVE_UPLOADS, LimitUnit.COUNT),
    OrganizationLimitDefinition(OrganizationLimit.ACTIVE_DOWNLOADS, LimitUnit.COUNT),
)


def validate_limit_overrides(value: object) -> dict[str, int]:
    """Validate explicit overrides once at the write boundary; absence means inheritance."""
    if not isinstance(value, dict):
        raise ValidationError(
            "Organization limits must be an object.", code="invalid_limits"
        )
    if value.keys() - set(OrganizationLimit.values):
        raise ValidationError(
            "One or more limits cannot be overridden.", code="invalid_limit_key"
        )
    try:
        limits = LimitsConfig.model_validate(value, strict=True)
    except PydanticValidationError as e:
        raise ValidationError(
            [
                f"{OrganizationLimit(error['loc'][0]).label}: {error['msg']}"
                for error in e.errors(include_input=False)
            ],
            code="invalid_limit_value",
        ) from None
    return {strKey: getattr(limits, strKey) for strKey in value}


def get_run_log_retention_days(organization: "Organization") -> int:
    """Apply the current deployment ceiling without changing the stored preference."""
    defaults = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return min(organization.run_log_retention_days, defaults.runLogRetentionDays)


def get_organization_limits(organization: "Organization") -> LimitsConfig:
    """Combine the current defaults with validated overrides from the loaded organization."""
    defaults = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if not organization.limit_overrides:
        return defaults
    return defaults.model_copy(update=organization.limit_overrides)
