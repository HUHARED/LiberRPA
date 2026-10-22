# FileName: capacity.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from console_project.workers import CAPACITY_CHECK_LOCK_ID, hold_worker_session
from notifications.capacity_emails import queue_capacity_notices
from organizations.models import Organization
from organizations.limits import get_organization_limits
from organizations.usage import get_organization_capacity_usage

from .capacity_contracts import (
    INT_CAPACITY_WARNING_PERCENT,
    INT_CAPACITY_RESET_PERCENT,
    INT_STORAGE_WARNING_BYTES,
    CapacityResource,
    CapacityLevel,
    CapacityCheckResult,
)
from .models import CapacityAlertState

_LOGGER = logging.getLogger("console.capacity")
_NOTICE_INTERVAL = timedelta(hours=24)


def _record_capacity(
    *,
    organization: Organization | None,
    resource: CapacityResource,
    used: int | None,
    reserved: int | None,
    limit: int | None,
    checkedAt: datetime,
    freeBytes: int | None = None,
) -> int:
    """Update one observation and enqueue a due notice in the same transaction."""
    state, _ = CapacityAlertState.objects.select_for_update().get_or_create(
        organization=organization, resource=resource
    )
    state.used = used
    state.reserved = reserved
    state.limit = limit
    state.free_bytes = freeBytes
    state.checked_at = checkedAt
    boolReset = False
    if used is None or reserved is None or limit is None:
        state.level = CapacityLevel.UNKNOWN
    elif resource == CapacityResource.STORAGE_VOLUME:
        if freeBytes is None:
            raise ValueError("A measured volume requires its available free space.")
        state.level = (
            CapacityLevel.WARNING
            if freeBytes < INT_STORAGE_WARNING_BYTES
            else CapacityLevel.NORMAL
        )
        boolReset = state.level == CapacityLevel.NORMAL
    else:
        intOccupied = used + reserved
        if limit == 0:
            # A disabled, empty resource is not an outage; existing data still merits a notice.
            state.level = (
                CapacityLevel.LIMIT_REACHED if intOccupied else CapacityLevel.NORMAL
            )
            boolReset = intOccupied == 0
        else:
            if intOccupied >= limit:
                state.level = CapacityLevel.LIMIT_REACHED
            elif intOccupied * 100 >= limit * INT_CAPACITY_WARNING_PERCENT:
                state.level = CapacityLevel.WARNING
            else:
                state.level = CapacityLevel.NORMAL
            boolReset = intOccupied * 100 < limit * INT_CAPACITY_RESET_PERCENT

    if boolReset:
        state.warning_notified_at = None
        state.limit_notified_at = None

    intQueued = 0
    if state.level in (CapacityLevel.WARNING, CapacityLevel.LIMIT_REACHED):
        notifiedAt = (
            state.warning_notified_at
            if state.level == CapacityLevel.WARNING
            else state.limit_notified_at
        )
        if notifiedAt is None or checkedAt >= notifiedAt + _NOTICE_INTERVAL:
            intQueued = queue_capacity_notices(state, organization)
            if intQueued:
                if state.level == CapacityLevel.WARNING:
                    state.warning_notified_at = checkedAt
                else:
                    state.limit_notified_at = checkedAt
    state.save(
        update_fields=[
            "level",
            "used",
            "reserved",
            "limit",
            "free_bytes",
            "checked_at",
            "warning_notified_at",
            "limit_notified_at",
        ]
    )
    return intQueued


@transaction.atomic
def _check_storage_capacity() -> tuple[bool, int]:
    pathStorage = Path(settings.CONSOLE_STORAGE_ROOT)
    intUsed: int | None = None
    intReserved: int | None = None
    intLimit: int | None = None
    intFreeBytes: int | None = None
    try:
        if pathStorage.is_dir():
            usage = shutil.disk_usage(pathStorage)
            intUsed, intReserved, intLimit = usage.used, 0, usage.total
            intFreeBytes = usage.free
        else:
            _LOGGER.warning(
                "Capacity check: the configured storage directory is unavailable."
            )
    except OSError:
        _LOGGER.exception("Capacity check could not read the file storage volume.")
    intQueued = _record_capacity(
        organization=None,
        resource=CapacityResource.STORAGE_VOLUME,
        used=intUsed,
        reserved=intReserved,
        limit=intLimit,
        checkedAt=timezone.now(),
        freeBytes=intFreeBytes,
    )
    return intUsed is not None, intQueued


@transaction.atomic
def _check_organization_capacity(organizationId: UUID) -> tuple[bool, int]:
    # Use the normal organization lock order; never lock all organizations together.
    organization = (
        Organization.objects
        .select_for_update()
        .filter(
            pk=organizationId,
            deletion_requested_at__isnull=True,
            deletion_started_at__isnull=True,
        )
        .first()
    )
    if organization is None:
        return False, 0
    limits = get_organization_limits(organization)
    dictUsage = get_organization_capacity_usage(organization)
    currentTime = timezone.now()
    intQueued = 0
    for key, (intUsed, intReserved) in dictUsage.items():
        intQueued += _record_capacity(
            organization=organization,
            resource=CapacityResource(key.value),
            used=intUsed,
            reserved=intReserved or 0,
            limit=getattr(limits, key.value),
            checkedAt=currentTime,
        )
    return True, intQueued


def check_capacity() -> CapacityCheckResult:
    """Check one volume and bounded per-organization balances without changing admission rules."""
    with hold_worker_session(lockId=CAPACITY_CHECK_LOCK_ID, workerName="capacity check"):
        boolStorageAvailable, intQueued = _check_storage_capacity()
        intOrganizationCount = 0
        # Keyset batches avoid retaining a cursor across per-organization commits.
        lastId: UUID | None = None
        while True:
            organizations = Organization.objects.filter(
                deletion_requested_at__isnull=True, deletion_started_at__isnull=True
            ).order_by("pk")
            if lastId is not None:
                organizations = organizations.filter(pk__gt=lastId)
            listId = list(organizations.values_list("pk", flat=True)[:200])
            if not listId:
                break
            for organizationId in listId:
                boolChecked, intOrganizationQueued = _check_organization_capacity(
                    organizationId
                )
                intOrganizationCount += int(boolChecked)
                intQueued += intOrganizationQueued
            lastId = listId[-1]
    return CapacityCheckResult(
        organizationCount=intOrganizationCount,
        queuedEmailCount=intQueued,
        storageAvailable=boolStorageAvailable,
    )
