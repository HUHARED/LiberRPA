# FileName: maintenance.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone

from console_project.recovery import (
    is_restored_service_pending_review,
    complete_restored_service_review,
)

from runs.contracts import JobState, RunStatus
from runs.models import Job, Run
from runs.worker_state import require_control_service
from schedules.cron import get_next_trigger
from schedules.models import Schedule, SchedulerState

from .audit import get_audit_snapshot, record_audit
from .contracts import AuditAction, ServiceState, MaintenanceAction
from .models import MaintenanceState, AuditScope

_INT_MAINTENANCE_LOCK_NAMESPACE = int.from_bytes(b"LRMT", "big")


@dataclass(frozen=True)
class MaintenanceStatus:
    state: ServiceState
    enteredAt: datetime | None
    activeJobs: int
    runningRuns: int
    jobsNeedingReview: int
    canResume: bool
    resumeBlockReason: str
    updatedAt: datetime


class ServiceMaintenanceError(ValidationError):
    def __init__(self) -> None:
        super().__init__(
            "Console is under maintenance. Try again after service resumes.",
            code="service_maintenance",
        )


def lock_maintenance_state(*, forUpdate: bool = False) -> MaintenanceState | None:
    """Share the short admission boundary; only maintenance changes need exclusive access."""
    if not connection.in_atomic_block:
        raise RuntimeError("Check the maintenance boundary inside a transaction.")
    if connection.vendor != "postgresql":
        raise ImproperlyConfigured("The maintenance boundary requires PostgreSQL.")
    strLock = "PG_ADVISORY_XACT_LOCK" if forUpdate else "PG_ADVISORY_XACT_LOCK_SHARED"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {strLock}(%s, %s)", [_INT_MAINTENANCE_LOCK_NAMESPACE, 1])
    return MaintenanceState.objects.filter(pk=1).first()


def require_service_normal() -> None:
    state = lock_maintenance_state()
    if is_restored_service_pending_review() or (
        state is not None and state.entered_at is not None
    ):
        raise ServiceMaintenanceError()


def get_resume_block_reason() -> str:
    currentTime = timezone.now()
    try:
        control = require_control_service(currentTime)
    except ValidationError:
        return "The run control worker is unavailable."
    if control.last_tick_at > currentTime:
        return "The run control activity time is in the future."
    if control.recovery_until is not None and currentTime < control.recovery_until:
        return "The run control worker is still recovering."
    return ""


def load_maintenance_status() -> MaintenanceStatus:
    state = MaintenanceState.objects.filter(pk=1).first()
    enteredAt = state.entered_at if state is not None else None
    boolMaintenance = enteredAt is not None or is_restored_service_pending_review()
    strResumeBlockReason = get_resume_block_reason() if boolMaintenance else ""
    dictJobCount = Job.objects.filter(closed_at__isnull=True).aggregate(
        active=Count("pk", filter=~Q(state=JobState.FINISHED)),
        review=Count("pk", filter=Q(state=JobState.NEEDS_REVIEW)),
    )
    return MaintenanceStatus(
        state=ServiceState.MAINTENANCE if boolMaintenance else ServiceState.NORMAL,
        enteredAt=enteredAt,
        activeJobs=dictJobCount["active"],
        runningRuns=Run.objects.filter(status=RunStatus.RUNNING).count(),
        jobsNeedingReview=dictJobCount["review"],
        canResume=boolMaintenance and not strResumeBlockReason,
        resumeBlockReason=strResumeBlockReason,
        updatedAt=timezone.now(),
    )


def update_maintenance(action: MaintenanceAction) -> bool:
    """Apply a server-side command under the same lock used by job admission."""
    with transaction.atomic():
        state = lock_maintenance_state(forUpdate=True)
        boolEnter = action == MaintenanceAction.ENTER
        boolRestored = is_restored_service_pending_review()
        boolEntered = state is not None and state.entered_at is not None
        if boolEnter == boolEntered and not (boolRestored and not boolEnter):
            return False
        if not boolEnter:
            strReason = get_resume_block_reason()
            if strReason:
                raise ValidationError(strReason, code="service_not_ready")
        if state is None:
            state = MaintenanceState.objects.create(pk=1)
        dictBefore = get_audit_snapshot(state)
        changedAt = timezone.now()
        state.entered_at = changedAt if boolEnter else None
        state.save(update_fields=["entered_at"])
        if boolRestored and not boolEnter:
            # Keep the file barrier until the future-only schedule boundary commits.
            for schedule in (
                Schedule.objects
                .select_for_update()
                .filter(enabled=True, deleted_at__isnull=True)
                .iterator()
            ):
                schedule.next_trigger_at = get_next_trigger(
                    schedule.cron,
                    schedule.time_zone,
                    schedule.active_from,
                    schedule.active_until,
                    changedAt,
                )
                schedule.save(update_fields=["next_trigger_at"])
            SchedulerState.objects.update_or_create(
                pk=1, defaults={"scanned_at": changedAt}
            )
            transaction.on_commit(complete_restored_service_review)
        record_audit(
            AuditAction.MAINTENANCE_ENTER
            if boolEnter
            else AuditAction.MAINTENANCE_RESUME,
            actor=None,
            organization=None,
            target=state,
            before=dictBefore,
            scope=AuditScope.PLATFORM,
            metadata={"command": f"maintenance {action.value}"},
        )
    return True
