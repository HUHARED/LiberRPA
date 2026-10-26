# FileName: events.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from executors.models import ExecutorSession
from packages.contracts import RunConflictPolicy, PackagePreparationState

from .contracts import (
    JobState,
    AssignmentState,
    RunStatus,
    OutputsStatus,
    RunEventKind,
    RunNotStartedReason,
    WorkStartedEvent,
    WorkEndedEvent,
    WorkUnknownEvent,
    WorkNotStartedEvent,
    WorkRecordingEvent,
    WorkEvent,
)
from .control_notifications import notify_executor_control
from .dispatch import get_start_evidence_not_before
from .models import Assignment, Run, RunEvent
from .services import (
    STR_SOURCE_ACCESS_REVOKED_REASON,
    has_job_source_access,
    finish_job,
    mark_job_needs_review,
)

_INT_RETRY_SECONDS = 60


def receive_event(session: ExecutorSession, event: WorkEvent) -> None:
    """Commit one stable event under the organization lock before acknowledging it."""
    from notifications.models import RunEmailEvent
    from notifications.run_events import notify_run_event
    from notifications.run_email import get_run_email_end_event

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
    startedAt = (
        event.started_at
        if isinstance(event, (WorkStartedEvent, WorkEndedEvent))
        else event.interrupted_started_at
        if isinstance(event, WorkUnknownEvent)
        else None
    )
    boolConfirmedInterruption = (
        isinstance(event, WorkUnknownEvent) and startedAt is not None
    )
    boolWasPreparing = assignment.state == AssignmentState.PREPARING
    if (
        assignment.state == AssignmentState.WITHDRAWN
        and event.kind
        in (
            RunEventKind.PREPARATION_FAILED,
            RunEventKind.NOT_STARTED,
            RunEventKind.UNKNOWN,
        )
        and not boolConfirmedInterruption
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
    if startedAt is not None:
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
        if (
            startedAt > assignment.permit_expires_at
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
            job.attempt_count = max(job.attempt_count, assignment.attempt_number)
            job.save(update_fields=["attempt_count"])
            if job.closed_at is None and not boolConfirmedInterruption:
                notify_run_event(run, event=RunEmailEvent.START)
        if isinstance(event, WorkEndedEvent) and run.ended_at is None:
            run.ended_at = event.occurred_at
            run.status = event.status
            run.reason = event.reason
            run.error_summary = event.error_summary
            run.outputs_status = event.outputs.status
            run.outputs = event.outputs.model_dump(mode="json")["values"]
            run.outputs_reason = event.outputs.reason
            run.outputs_unavailable_keys = event.outputs.unavailable_keys
            emailContext = event.email_output_context
            setEmailOutputKey = set(
                job.run_snapshot["email_output_keys"].get(event.status, [])
            )
            run.email_output_context = (
                [entry.model_dump(mode="json") for entry in emailContext]
                if emailContext is not None
                and {entry.key for entry in emailContext} == setEmailOutputKey
                else None
            )
            run.save()
            assignment.state = AssignmentState.FINISHED
            assignment.reason = event.reason
            assignment.save(update_fields=["state", "reason"])
            if job.closed_at is None:
                emailEvent = get_run_email_end_event(run.status)
                if emailEvent is not None:
                    notify_run_event(run, event=emailEvent)
                boolRunRetryable = (
                    run.status in (RunStatus.ERROR, RunStatus.TIMED_OUT)
                    and job.stop_requested_at is None
                    and assignment.attempt_number <= job.max_retry_count
                )
                if boolRunRetryable and has_job_source_access(job):
                    job.state = JobState.WAITING_RETRY
                    job.retry_at = timezone.now() + timedelta(seconds=_INT_RETRY_SECONDS)
                    job.attempt_queued_at = job.retry_at
                    job.reason = (
                        f"Waiting {_INT_RETRY_SECONDS} seconds before the next attempt."
                    )
                    job.save(
                        update_fields=["state", "retry_at", "attempt_queued_at", "reason"]
                    )
                else:
                    strReason = event.reason or f"Run {run.status}."
                    if boolRunRetryable:
                        strReason = (
                            f"{strReason[:1800]}\n"
                            "No retry was scheduled because this Job no longer has run permission."
                        )
                    finish_job(job, strReason)
        elif boolConfirmedInterruption and run.ended_at is None:
            run.status = RunStatus.INTERRUPTED
            run.reason = event.reason or (
                "The Python process has exited, but its result and end time are unavailable."
            )
            run.outputs_status = OutputsStatus.UNAVAILABLE
            run.outputs_reason = "Python did not publish a final output snapshot."
            run.save(
                update_fields=["status", "reason", "outputs_status", "outputs_reason"]
            )
            assignment.state = AssignmentState.NEEDS_REVIEW
            assignment.reason = run.reason
            assignment.save(update_fields=["state", "reason"])
            mark_job_needs_review(job, assignment, reason=run.reason)
        elif event.kind == RunEventKind.STARTED and run.status == RunStatus.RUNNING:
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
            PackagePreparationState.FAILED,
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
    elif isinstance(event, WorkNotStartedEvent):
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
                    AssignmentState.NEEDS_REVIEW,
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
                        "This Job no longer has run permission.",
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
            assignment.reason = event.reason or "The run did not start."
            assignment.save(update_fields=["state", "reason"])
            if job.state != JobState.FINISHED:
                finish_job(job, assignment.reason, notify=job.stop_requested_at is None)
    elif isinstance(event, WorkRecordingEvent):
        run = Run.objects.get(assignment=assignment)
        run.recording = event.recording.model_dump(mode="json")
        run.save(update_fields=["recording"])
    elif event.kind == RunEventKind.UNKNOWN:
        if assignment.state not in (AssignmentState.FINISHED, AssignmentState.WITHDRAWN):
            assignment.state = AssignmentState.NEEDS_REVIEW
            assignment.reason = (
                event.reason
                or "Unable to confirm whether the run started or finished. Check the Executor."
            )
            assignment.save(update_fields=["state", "reason"])
            mark_job_needs_review(job, assignment, reason=assignment.reason)
    RunEvent.objects.create(
        id=event.event_id,
        assignment=assignment,
        kind=event.kind,
        occurred_at=event.occurred_at,
        reason=event.reason,
    )
    if (boolWasPreparing and assignment.state != AssignmentState.PREPARING) or (
        isinstance(event, WorkNotStartedEvent)
        and event.not_started_reason == RunNotStartedReason.LOCAL_CONFLICT
    ):
        notify_executor_control(assignment.executor_id)
