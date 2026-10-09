# FileName: worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
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
from .models import Schedule, SchedulerState, ScheduleTrigger, TriggerStatus

_INT_NORMAL_LATENESS_SECONDS = 5
_INT_RECOVERY_SECONDS = 600
_INT_TRIGGER_BATCH_SIZE = 100


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
        title="Schedule could not execute",
        detail=f"Schedule: {schedule.name}\nScheduled at: {scheduledAt.isoformat()}\nReason: {reason}",
        eventKey=f"schedule:{schedule.pk}:{scheduledAt.isoformat()}",
    )


def _process_trigger(
    organizationId: uuid.UUID,
    scheduleId: uuid.UUID,
    scheduledAt: datetime,
    *,
    recoveryFrom: datetime | None,
    recoveryUntil: datetime | None,
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
        # Lock waits count toward normal lateness, not the fixed recovery interval.
        currentTime = timezone.now()
        if scheduledAt > currentTime:
            return
        boolRecoveryPoint = recoveryUntil is not None and scheduledAt <= recoveryUntil
        boolCanRecover = (
            boolRecoveryPoint
            and recoveryFrom is not None
            and recoveryUntil is not None
            and recoveryUntil - recoveryFrom <= timedelta(seconds=_INT_RECOVERY_SECONDS)
            and schedule.updated_at <= recoveryFrom
        )
        if not is_organization_business_available(organization):
            _advance(schedule, currentTime)
            return
        if boolRecoveryPoint and not boolCanRecover:
            strReason = "The trigger service interruption exceeded 600 seconds, or the Schedule changed during the interruption. No missed triggers were replayed."
        elif not boolCanRecover and currentTime - scheduledAt > timedelta(
            seconds=_INT_NORMAL_LATENESS_SECONDS
        ):
            strReason = f"The scheduler missed the normal {_INT_NORMAL_LATENESS_SECONDS}-second trigger tolerance."
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
            # One receipt describes the skipped interval; do not iterate millions of missed seconds.
            _advance(
                schedule,
                recoveryUntil
                if boolRecoveryPoint and recoveryUntil is not None
                else currentTime,
            )
            return
        if ScheduleTrigger.objects.filter(
            schedule_id=schedule.pk, scheduled_at=scheduledAt
        ).exists():
            _advance(schedule, scheduledAt)
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
    *, recoveryFrom: datetime | None = None, recoveryUntil: datetime | None = None
) -> bool:
    """Process a bounded batch in trigger order; return whether more due points remain."""
    scanUntil = timezone.now()
    query = Schedule.objects.filter(
        enabled=True, deleted_at__isnull=True, next_trigger_at__lte=scanUntil
    ).order_by("next_trigger_at", "id")
    for _ in range(_INT_TRIGGER_BATCH_SIZE):
        # Advancing one Schedule may reveal the next earliest point across all Schedules.
        nextTrigger = query.values_list(
            "department__organization_id", "id", "next_trigger_at"
        ).first()
        if nextTrigger is None:
            break
        organizationId, scheduleId, scheduledAt = nextTrigger
        _process_trigger(
            organizationId,
            scheduleId,
            scheduledAt,
            recoveryFrom=recoveryFrom,
            recoveryUntil=recoveryUntil,
        )
    boolMore = query.exists()
    if not boolMore:
        # Later points were outside this scan and must not be included in its checkpoint.
        SchedulerState.objects.update_or_create(pk=1, defaults={"scanned_at": scanUntil})
    return boolMore


def get_recovery_boundary() -> tuple[datetime | None, datetime]:
    recoveryUntil = timezone.now()
    state = SchedulerState.objects.filter(pk=1).first()
    return (None if state is None else state.scanned_at), recoveryUntil
