# FileName: maintenance.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone

from console_project.recovery import is_restored_service_pending_review

from runs.contracts import JobState, RunStatus
from runs.models import Job, Run
from runs.dispatch_control import require_control_service

from .contracts import ServiceState, MaintenanceResponse
from .models import MaintenanceState

_INT_MAINTENANCE_LOCK_NAMESPACE = int.from_bytes(b"LRMT", "big")


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


def load_maintenance_status() -> MaintenanceResponse:
    state = MaintenanceState.objects.filter(pk=1).first()
    enteredAt = state.entered_at if state is not None else None
    boolMaintenance = enteredAt is not None or is_restored_service_pending_review()
    strResumeBlockReason = get_resume_block_reason() if boolMaintenance else ""
    dictJobCount = Job.objects.filter(closed_at__isnull=True).aggregate(
        active=Count("pk", filter=~Q(state=JobState.FINISHED)),
        review=Count("pk", filter=Q(state=JobState.NEEDS_REVIEW)),
    )
    return MaintenanceResponse(
        state=ServiceState.MAINTENANCE if boolMaintenance else ServiceState.NORMAL,
        entered_at=enteredAt,
        active_jobs=dictJobCount["active"],
        running_runs=Run.objects.filter(status=RunStatus.RUNNING).count(),
        jobs_needing_review=dictJobCount["review"],
        can_resume=boolMaintenance and not strResumeBlockReason,
        resume_block_reason=strResumeBlockReason,
        updated_at=timezone.now(),
    )
