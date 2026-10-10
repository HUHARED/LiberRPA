# FileName: worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from organizations.models import Organization
from organizations.permissions import is_organization_business_available

from packages.runtime import build_run_settings
from runs.models import JobSource
from runs.admission import accept_request

from .cron import get_next_trigger
from .models import TriggerStatus, Schedule, ScheduleTrigger, SchedulerState

_INT_RECOVERY_SECONDS = 600
_INT_TRIGGER_BATCH_SIZE = 100


@dataclass
class ScheduleScanWindow:
    """Keep one scan interval across bounded batches, including its first lock wait."""

    previousScanAt: datetime | None
    until: datetime | None = None


def _advance(schedule: Schedule, after: datetime) -> None:
    schedule.next_trigger_at = get_next_trigger(
        schedule.cron,
        schedule.time_zone,
        schedule.active_from,
        schedule.active_until,
        after,
    )
    schedule.save(update_fields=["next_trigger_at"])


def _notify_failure(
    schedule: Schedule, organizationId: uuid.UUID, scheduledAt: datetime, reason: str
) -> None:
    from notifications.services import notify_prestart_failure

    notify_prestart_failure(
        organizationId=organizationId,
        departmentId=schedule.department_id,
        creatorId=schedule.created_by_id,
        source=JobSource.SCHEDULE,
        title="Schedule could not execute",
        detail=f"Schedule: {schedule.name}\nScheduled at: {scheduledAt.isoformat()}\nReason: {reason}",
        eventKey=f"schedule:{schedule.pk}:{scheduledAt.isoformat()}",
    )


def _process_trigger(
    organizationId: uuid.UUID,
    scheduleId: uuid.UUID,
    scheduledAt: datetime,
    *,
    scanWindow: ScheduleScanWindow,
) -> None:
    with transaction.atomic():
        organization = (
            Organization.objects.select_for_update().filter(pk=organizationId).first()
        )
        if organization is None:
            return
        schedule = Schedule.objects.select_for_update().filter(pk=scheduleId).first()
        if (
            schedule is None
            or not schedule.enabled
            or schedule.deleted_at is not None
            or schedule.next_trigger_at != scheduledAt
        ):
            return
        currentTime = timezone.now()
        if scheduledAt > currentTime:
            return
        # Freeze the interval only after its first valid candidate has acquired both locks.
        if scanWindow.until is None:
            scanWindow.until = currentTime
        scanUntil = scanWindow.until
        if not is_organization_business_available(organization):
            _advance(schedule, currentTime)
            return
        if ScheduleTrigger.objects.filter(
            schedule_id=schedule.pk, scheduled_at=scheduledAt
        ).exists():
            _advance(schedule, scheduledAt)
            return
        skipUntil = scanUntil
        if scanWindow.previousScanAt is None:
            strReason = "No previous Schedule scan time is available. Missed triggers were skipped."
        elif scanUntil - scanWindow.previousScanAt > timedelta(
            seconds=_INT_RECOVERY_SECONDS
        ):
            strReason = "Schedule processing was interrupted for more than 10 minutes. Missed triggers in this interval were skipped."
        elif schedule.updated_at > scheduledAt:
            # Do not apply new settings to past points; keep future points of the revised Schedule.
            strReason = "The Schedule changed after this trigger time. Earlier missed triggers were skipped."
            skipUntil = schedule.updated_at
        else:
            strReason = ""
        if strReason:
            ScheduleTrigger.objects.get_or_create(
                schedule_id=schedule.pk,
                scheduled_at=scheduledAt,
                defaults={
                    "organization_id": organizationId,
                    "status": TriggerStatus.MISSED,
                    "reason": strReason,
                },
            )
            _notify_failure(schedule, organizationId, scheduledAt, strReason)
            # One receipt describes skipped points; never replay the tail of a long interruption.
            _advance(schedule, skipUntil)
            return
        clientRequestId = uuid.uuid4()
        try:
            # A savepoint prevents partial Job acceptance if a current input or target fails validation.
            with transaction.atomic():
                jobRequest = accept_request(
                    organizationId=organizationId,
                    departmentId=schedule.department_id,
                    packageId=schedule.package_id,
                    settings=build_run_settings(schedule),
                    executorIds=[
                        uuid.UUID(strValue) for strValue in schedule.executor_ids
                    ],
                    groupId=schedule.group_id,
                    source=JobSource.SCHEDULE,
                    actorId=schedule.created_by_id,
                    clientRequestId=clientRequestId,
                    scheduleId=schedule.pk,
                    scheduleName=schedule.name,
                    scheduledAt=scheduledAt,
                )
            ScheduleTrigger.objects.create(
                organization_id=organizationId,
                schedule_id=schedule.pk,
                scheduled_at=scheduledAt,
                status=TriggerStatus.ACCEPTED,
                job_request_id=jobRequest.pk,
            )
        except (ValidationError, PermissionDenied, ObjectDoesNotExist) as e:
            strReason = " ".join(e.messages) if isinstance(e, ValidationError) else str(e)
            strReason = (strReason or "The configured resource is unavailable.")[:1000]
            ScheduleTrigger.objects.create(
                organization_id=organizationId,
                schedule_id=schedule.pk,
                scheduled_at=scheduledAt,
                status=TriggerStatus.REJECTED,
                reason=strReason,
            )
            if getattr(e, "code", None) != "target_paused":
                _notify_failure(schedule, organizationId, scheduledAt, strReason)
        _advance(schedule, scheduledAt)


def scan_schedules(
    scanWindow: ScheduleScanWindow | None = None,
) -> ScheduleScanWindow | None:
    """Return the same interval while more points remain, or None after saving its boundary."""
    if scanWindow is None:
        state = SchedulerState.objects.filter(pk=1).first()
        scanWindow = ScheduleScanWindow(
            previousScanAt=None if state is None else state.scanned_at
        )
    scanStartedAt = timezone.now()
    query = Schedule.objects.filter(enabled=True, deleted_at__isnull=True).order_by(
        "next_trigger_at", "id"
    )
    for _ in range(_INT_TRIGGER_BATCH_SIZE):
        # Advancing one Schedule may reveal the next earliest point across all Schedules.
        nextTrigger = (
            query
            .filter(next_trigger_at__lte=scanWindow.until or scanStartedAt)
            .values_list("department__organization_id", "id", "next_trigger_at")
            .first()
        )
        if nextTrigger is None:
            break
        organizationId, scheduleId, scheduledAt = nextTrigger
        _process_trigger(
            organizationId,
            scheduleId,
            scheduledAt,
            scanWindow=scanWindow,
        )
    scanUntil = scanWindow.until or scanStartedAt
    if query.filter(next_trigger_at__lte=scanUntil).exists():
        return scanWindow
    # Do not include time spent draining the batch in the completed scan boundary.
    SchedulerState.objects.update_or_create(pk=1, defaults={"scanned_at": scanUntil})
    return None
