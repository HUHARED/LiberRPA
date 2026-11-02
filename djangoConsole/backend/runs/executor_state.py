# FileName: executor_state.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import timedelta

from django.utils import timezone

from executors.models import ExecutorSession

from .contracts import WorkSyncRequest, RunStatus
from .models import ExecutorWorkState, Run
from .services import confirm_run_running
from .browser_events import notify_jobs_changed

INT_WORK_STATE_MAX_AGE_SECONDS = 45


def has_current_run_report(session: ExecutorSession, runId: uuid.UUID) -> bool:
    """Reuse a recent positive report while the caller holds this valid association's lock."""
    work = (
        ExecutorWorkState.objects
        .filter(
            executor_id=session.executor_id,
            session_id=session.id,
            reported_at__gte=timezone.now()
            - timedelta(seconds=INT_WORK_STATE_MAX_AGE_SECONDS),
        )
        .only("running_run_ids")
        .first()
    )
    return work is not None and str(runId) in work.running_run_ids


def update_executor_work_state(
    session: ExecutorSession, payload: WorkSyncRequest
) -> None:
    """Save a validated report inside the caller's locked association transaction."""
    currentTime = timezone.now()
    listRunningRunId = [str(entry) for entry in payload.running_run_ids]
    work, boolCreated = ExecutorWorkState.objects.get_or_create(
        executor_id=session.executor_id,
        defaults={
            "session_id": session.id,
            "reported_at": currentTime,
            "running_run_ids": listRunningRunId,
            "local_waiting_count": payload.local_waiting_count,
            "other_active_run_count": payload.other_active_run_count,
        },
    )
    if not boolCreated:
        # Freshness is a new fact on every report; unchanged occupancy is not.
        work.reported_at = currentTime
        listUpdateField = ["reported_at"]
        if work.session_id != session.id:
            work.session_id = session.id
            listUpdateField.append("session_id")
        if work.running_run_ids != listRunningRunId:
            work.running_run_ids = listRunningRunId
            listUpdateField.append("running_run_ids")
        if work.local_waiting_count != payload.local_waiting_count:
            work.local_waiting_count = payload.local_waiting_count
            listUpdateField.append("local_waiting_count")
        if work.other_active_run_count != payload.other_active_run_count:
            work.other_active_run_count = payload.other_active_run_count
            listUpdateField.append("other_active_run_count")
        work.save(update_fields=listUpdateField)

    setChangedJobId: set[uuid.UUID] = set()
    for run in Run.objects.filter(
        assignment__session_id=session.id,
        assignment__executor_id=session.executor_id,
        id__in=payload.running_run_ids,
        status=RunStatus.UNCONFIRMED,
    ).select_related("assignment", "job"):
        confirm_run_running(run)
        setChangedJobId.add(run.job_id)
    notify_jobs_changed(setChangedJobId)
