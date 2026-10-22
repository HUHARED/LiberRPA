# FileName: worker_state.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .contracts import JobState, AssignmentState
from .models import Job, ExecutorWorkState, Assignment, DispatchControl
from .control_notifications import notify_executor_control

_INT_CONTROL_MAX_AGE_SECONDS = 15


def require_control_service(currentTime: datetime) -> DispatchControl:
    control = DispatchControl.objects.filter(pk=1).first()
    if control is None or control.last_tick_at < currentTime - timedelta(
        seconds=_INT_CONTROL_MAX_AGE_SECONDS
    ):
        raise ValidationError(
            "The run control worker is unavailable.", code="control_service_unavailable"
        )
    return control


def start_control_cycle() -> None:
    with transaction.atomic():
        currentTime = timezone.now()
        control, _ = DispatchControl.objects.select_for_update().get_or_create(pk=1)
        control.cycle_started_at = currentTime
        control.last_tick_at = currentTime
        control.recovery_until = currentTime + timedelta(seconds=60)
        control.save()
        # After restart, assignments without start permission can be withdrawn; check existing permissions before changing their state.
        listJobId = list(
            Assignment.objects.filter(state=AssignmentState.PREPARING).values_list(
                "job_id", flat=True
            )
        )
        Assignment.objects.filter(state=AssignmentState.PREPARING).update(
            state=AssignmentState.WITHDRAWN,
            reason="Control service restarted before permission.",
        )
        Job.objects.filter(pk__in=listJobId, state=JobState.PREPARING).update(
            state=JobState.WAITING
        )
        # Every connected Executor must report fresh work state for this control cycle.
        for executorId in ExecutorWorkState.objects.values_list("executor_id", flat=True):
            notify_executor_control(executorId)
