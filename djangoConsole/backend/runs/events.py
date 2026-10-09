# FileName: events.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from executors.models import ExecutorSession
from packages.contracts import RunConflictPolicy

from .models import (
    JobState,
    AssignmentState,
    RunResult,
    RunEventKind,
    Assignment,
    Run,
    RunEvent,
)
from .contracts import RunNotStartedReason, WorkEvent
from .control_notifications import notify_executor_control
from .dispatch import get_start_evidence_not_before
from .services import (
    STR_SOURCE_ACCESS_REVOKED_REASON,
    has_job_source_access,
    finish_job,
)

_INT_RETRY_SECONDS = 60


def receive_event(session: ExecutorSession, event: WorkEvent) -> None:
    """Commit one stable event under the organization lock before acknowledging it."""
    from notifications.run_events import notify_run_event

    assignment = (
        Assignment.objects
        .select_for_update()
        .select_related("job__request")
        .get(
            pk=event.assignment_id, session_id=session.id, executor_id=session.executor_id
        )
    )
    previous = RunEvent.objects.filter(pk=event.event_id).first()
    if previous:
        if previous.assignment_id != assignment.id:
            raise ValidationError(
                "The event identity belongs to another assignment.",
                code="event_identity_conflict",
            )
        return
    job = assignment.job
    boolWasPreparing = assignment.state == AssignmentState.PREPARING
    if assignment.state == AssignmentState.WITHDRAWN and event.kind in (
        RunEventKind.PREPARATION_FAILED,
        RunEventKind.NOT_STARTED,
        RunEventKind.UNKNOWN,
    ):
        # A delayed reply to a withdrawn offer cannot affect a later assignment of the same Job.
        RunEvent.objects.create(
            id=event.event_id,
            assignment=assignment,
            kind=event.kind,
            occurred_at=event.occurred_at,
            reason=event.reason,
        )
        return
    if event.kind in (RunEventKind.STARTED, RunEventKind.ENDED):
        if (
            assignment.state
            in (
                AssignmentState.WITHDRAWN,
                AssignmentState.FINISHED,
            )
            and RunEvent.objects.filter(
                assignment=assignment, kind=RunEventKind.NOT_STARTED
            ).exists()
        ):
            raise ValidationError(
                "The client already confirmed that no process was created.",
                code="conflicting_start_evidence",
            )
        if assignment.permit_expires_at is None:
            raise ValidationError(
                "No start permission was issued for this assignment.",
                code="permission_required",
            )
        startedAt = (
            event.started_at
            if event.kind == RunEventKind.ENDED
            else (event.started_at or event.occurred_at)
        )
        if (
            startedAt is None
            or startedAt > assignment.permit_expires_at
            or startedAt < get_start_evidence_not_before(assignment.permit_expires_at)
        ):
            raise ValidationError(
                "The reported start is outside this permission window.",
                code="invalid_start_evidence",
            )
        run, boolCreated = Run.objects.get_or_create(
            id=assignment.run_id,
            defaults={"job": job, "assignment": assignment, "started_at": startedAt},
        )
        if boolCreated:
            job.attempts = max(job.attempts, assignment.attempt)
            job.save(update_fields=["attempts"])
            if job.closed_at is None:
                notify_run_event(run, event="start")
        if event.kind == RunEventKind.ENDED and run.ended_at is None:
            run.ended_at = event.occurred_at
            run.result = event.result
            run.reason = event.reason
            run.error_summary = event.error_summary
            if event.recording is not None:
                run.recording = event.recording.model_dump(mode="json")
            run.outputs_status = event.outputs.status
            run.outputs = event.outputs.model_dump(mode="json")["values"]
            run.outputs_reason = event.outputs.reason
            run.outputs_unavailable_keys = event.outputs.unavailable_keys
            run.save()
            assignment.state = AssignmentState.FINISHED
            assignment.reason = event.reason
            assignment.save(update_fields=["state", "reason"])
            if job.closed_at is None:
                if run.result in (RunResult.COMPLETED, RunResult.ERROR):
                    notify_run_event(run, event=str(run.result))
                boolRunRetryable = (
                    run.result == RunResult.ERROR
                    and job.stop_requested_at is None
                    and assignment.attempt <= job.retry_count
                )
                if boolRunRetryable and has_job_source_access(job):
                    job.state = JobState.RETRY
                    job.retry_at = timezone.now() + timedelta(seconds=_INT_RETRY_SECONDS)
                    job.attempt_queued_at = job.retry_at
                    job.reason = "Waiting 60 seconds before the next attempt."
                    job.save(
                        update_fields=["state", "retry_at", "attempt_queued_at", "reason"]
                    )
                else:
                    strReason = event.reason or f"Run {run.result}."
                    if boolRunRetryable:
                        strReason = (
                            f"{strReason[:1800]}\n"
                            "No retry was scheduled because the initiating account lost run permission."
                        )
                    finish_job(job, strReason)
        elif event.kind == RunEventKind.STARTED and run.ended_at is None:
            assignment.state = AssignmentState.RUNNING
            assignment.save(update_fields=["state"])
            if job.closed_at is None:
                job.state = (
                    JobState.STOPPING if job.stop_requested_at else JobState.RUNNING
                )
                job.reason = (
                    STR_SOURCE_ACCESS_REVOKED_REASON
                    if job.source_access_revoked_at is not None
                    else ""
                )
                job.save(update_fields=["state", "reason"])
    elif event.kind == RunEventKind.PREPARATION_FAILED:
        if assignment.permit_expires_at is not None:
            raise ValidationError(
                "A permitted assignment requires execution evidence.",
                code="invalid_preparation_event",
            )
        from packages.preparation import record_package_preparation

        record_package_preparation(
            job.package_id,
            assignment.executor_id,
            session.id,
            job.run_snapshot["python_environment_name"],
            "failed",
            event.reason,
        )
        assignment.state = AssignmentState.FINISHED
        assignment.reason = event.reason or "Package preparation failed."
        assignment.save(update_fields=["state", "reason"])
        if job.state != JobState.FINISHED:
            if job.target_group_id:
                job.state = JobState.WAITING
                job.reason = assignment.reason
                job.save(update_fields=["state", "reason"])
            else:
                finish_job(job, assignment.reason, notify=True)
    elif event.kind == RunEventKind.NOT_STARTED:
        if Run.objects.filter(assignment=assignment).exists():
            raise ValidationError(
                "An actual Run already exists.", code="actual_run_exists"
            )
        if event.not_started_reason == RunNotStartedReason.LOCAL_CONFLICT:
            strPolicy = job.run_snapshot["run_conflict_policy"]
            if (
                assignment.permit_expires_at is None
                or assignment.state
                not in (
                    AssignmentState.PERMITTED,
                    AssignmentState.REVIEW,
                )
                or strPolicy not in (RunConflictPolicy.WAIT, RunConflictPolicy.SKIP)
            ):
                raise ValidationError(
                    "A local conflict requires an unused Wait or Skip start permission.",
                    code="invalid_start_conflict",
                )
            # Keep the issued permit as evidence, but withdraw its right to start or be retried.
            assignment.state = AssignmentState.WITHDRAWN
            assignment.reason = (
                "Skipped because local running or waiting work has priority."
                if strPolicy == RunConflictPolicy.SKIP
                else "Waiting for local running or waiting work to finish."
            )
            assignment.save(update_fields=["state", "reason"])
            if job.state != JobState.FINISHED and job.closed_at is None:
                if job.stop_requested_at is not None:
                    finish_job(job, "Canceled before process creation.")
                elif not has_job_source_access(job):
                    finish_job(
                        job,
                        "The source account no longer has permission to run this Job.",
                        notify=True,
                    )
                elif strPolicy == RunConflictPolicy.SKIP:
                    finish_job(job, assignment.reason)
                else:
                    job.state = JobState.WAITING
                    job.reason = assignment.reason
                    job.retry_at = None
                    job.save(update_fields=["state", "reason", "retry_at"])
        else:
            assignment.state = AssignmentState.FINISHED
            assignment.reason = (
                event.reason or "The client confirmed no process was created."
            )
            assignment.save(update_fields=["state", "reason"])
            if job.state != JobState.FINISHED:
                finish_job(job, assignment.reason, notify=job.stop_requested_at is None)
    elif event.kind == RunEventKind.RECORDING:
        run = Run.objects.get(assignment=assignment)
        if event.recording is None:
            raise ValidationError(
                "A recording event requires current recording facts.",
                code="invalid_recording_event",
            )
        run.recording = event.recording.model_dump(mode="json")
        run.save(update_fields=["recording"])
    elif event.kind == RunEventKind.UNKNOWN:
        if assignment.state not in (AssignmentState.FINISHED, AssignmentState.WITHDRAWN):
            assignment.state = AssignmentState.REVIEW
            assignment.reason = (
                event.reason
                or "The client cannot confirm whether execution started or ended."
            )
            assignment.save(update_fields=["state", "reason"])
            if job.state != JobState.FINISHED:
                job.state = JobState.REVIEW
                job.reason = assignment.reason
                job.save(update_fields=["state", "reason"])
    RunEvent.objects.create(
        id=event.event_id,
        assignment=assignment,
        kind=event.kind,
        occurred_at=event.occurred_at,
        reason=event.reason,
    )
    if (
        boolWasPreparing and assignment.state != AssignmentState.PREPARING
    ) or event.not_started_reason == RunNotStartedReason.LOCAL_CONFLICT:
        notify_executor_control(assignment.executor_id)
