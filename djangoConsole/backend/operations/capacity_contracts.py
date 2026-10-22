# FileName: capacity_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from dataclasses import dataclass

from django.db.models import TextChoices

from organizations.limits import OrganizationLimit

INT_CAPACITY_CHECK_SECONDS = 3600
INT_CAPACITY_WARNING_PERCENT = 80
INT_CAPACITY_RESET_PERCENT = 70
INT_STORAGE_WARNING_BYTES = 10 * 1024**3


class CapacityResource(TextChoices):
    STORAGE_VOLUME = "storage_volume", "File Storage Volume"
    STORED_BYTES = (
        OrganizationLimit.STORED_BYTES.value,
        OrganizationLimit.STORED_BYTES.label,
    )
    QUEUE_ITEMS = (
        OrganizationLimit.QUEUE_ITEMS.value,
        OrganizationLimit.QUEUE_ITEMS.label,
    )
    QUEUE_DATA_BYTES = (
        OrganizationLimit.QUEUE_DATA_BYTES.value,
        OrganizationLimit.QUEUE_DATA_BYTES.label,
    )
    RUN_LOG_BYTES = (
        OrganizationLimit.RUN_LOG_BYTES.value,
        OrganizationLimit.RUN_LOG_BYTES.label,
    )
    RUN_LOG_GROUPS = (
        OrganizationLimit.RUN_LOG_GROUPS.value,
        OrganizationLimit.RUN_LOG_GROUPS.label,
    )
    RUN_HISTORY = (
        OrganizationLimit.RUN_HISTORY.value,
        OrganizationLimit.RUN_HISTORY.label,
    )


class CapacityLevel(TextChoices):
    NORMAL = "normal", "Normal"
    WARNING = "warning", "Warning"
    LIMIT_REACHED = "limit_reached", "Limit Reached"
    UNKNOWN = "unknown", "Unknown"


@dataclass(frozen=True)
class CapacityCheckResult:
    organizationCount: int
    queuedEmailCount: int
    storageAvailable: bool
