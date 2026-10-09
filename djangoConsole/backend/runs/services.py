# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from console_project.constants import INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH
from executors.contracts import ExecutorAssociationStatus
from executors.models import Executor, ExecutorGroup, ExecutorGroupMember, ExecutorSession
from executors.session_state import (
    get_current_executor_sessions,
    get_executor_association_status,
)
from organizations.models import DepartmentRole, Organization
from organizations.permissions import (
    AccessChannel,
    get_authorized_departments,
    require_organization_business_available,
    resolve_organization_access,
)
from packages.contracts import RunConflictPolicy

from .contracts import RunNotStartedReason, WorkEvent
from .control_notifications import notify_executor_control
from .dispatch_control import require_control_service
from .models import (
    Assignment,
    AssignmentState,
    DispatchControl,
    ExecutorWorkState,
    Job,
    JobSource,
    JobState,
    Run,
    RunEvent,
    RunEventKind,
    RunResult,
)

_INT_PERMIT_SECONDS = 15
_INT_START_EVIDENCE_TOLERANCE_SECONDS = 5
_INT_RETRY_SECONDS = 60
_INT_WORK_STATE_STALE_SECONDS = 45
_STR_SOURCE_ACCESS_REVOKED_REASON = (
    "The initiating account lost run permission; no further attempts will be scheduled."
)
_ACTIVE_ASSIGNMENT_STATES = (
    AssignmentState.PREPARING,
    AssignmentState.PERMITTED,
    AssignmentState.RUNNING,
    AssignmentState.REVIEW,
)


def _has_source_access(
    job: Job,
    *,
    sourceDepartmentIdsByActor: dict[uuid.UUID, set[uuid.UUID]] | None = None,
) -> bool:
    """Share source departments only within one locked organization dispatch pass."""
    if job.request.source == JobSource.SCHEDULE:
        return True
    actorId = job.request.actor_id
    if job.source_access_revoked_at is not None or actorId is None:
        return False
    if sourceDepartmentIdsByActor is not None and actorId in sourceDepartmentIdsByActor:
        return job.department_id in sourceDepartmentIdsByActor[actorId]
    try:
        access = resolve_organization_access(
            actorId=actorId,
            organizationId=job.request.organization_id,
            channel=AccessChannel.SESSION,
        )
        departmentQuery = get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        )
        if sourceDepartmentIdsByActor is None:
            # Permits and event processing recheck their own current operation, without sharing a cache.
            return departmentQuery.filter(pk=job.department_id).exists()
        setDepartmentId: set[uuid.UUID] = set(
            departmentQuery.values_list("id", flat=True)
        )
    except PermissionDenied:
        setDepartmentId = set()
    if sourceDepartmentIdsByActor is not None:
        sourceDepartmentIdsByActor[actorId] = setDepartmentId
    return job.department_id in setDepartmentId


def _finish_job(job: Job, reason: str, *, notify: bool = False) -> None:
    job.state = JobState.FINISHED
    job.reason = reason[:2000]
    job.ended_at = timezone.now()
    job.retry_at = None
    job.save(update_fields=["state", "reason", "ended_at", "retry_at"])
    if notify:
        from notifications.run_events import notify_job_failure

        notify_job_failure(job)


def _revoke_source_job(job: Job, currentTime: datetime) -> None:
    """Persist lost source authority without inventing a stop or an execution result."""
    if job.state == JobState.FINISHED or job.source_access_revoked_at is not None:
        return
    job.source_access_revoked_at = currentTime
    job.retry_at = None
    job.reason = (
        f"{job.reason[:1800]}\n{_STR_SOURCE_ACCESS_REVOKED_REASON}"
        if job.reason
        else _STR_SOURCE_ACCESS_REVOKED_REASON
    )
    job.save(update_fields=["source_access_revoked_at", "retry_at", "reason"])
    assignment = Assignment.objects.filter(
        job=job, state__in=_ACTIVE_ASSIGNMENT_STATES
    ).first()
    if assignment is not None and assignment.state != AssignmentState.PREPARING:
        # An issued permit may already have produced a process; retain its evidence and active state.
        return
    if assignment is not None:
        assignment.state = AssignmentState.WITHDRAWN
        assignment.reason = _STR_SOURCE_ACCESS_REVOKED_REASON
        assignment.stop_requested_at = assignment.stop_requested_at or currentTime
        assignment.save(update_fields=["state", "reason", "stop_requested_at"])
        notify_executor_control(assignment.executor_id)
    _finish_job(job, _STR_SOURCE_ACCESS_REVOKED_REASON, notify=True)


def reconcile_source_access(userId: uuid.UUID, organizationId: uuid.UUID) -> None:
    """Revoke only this account's ineligible Jobs inside the permission change's organization lock."""
    jobQuery = Job.objects.filter(
        request__organization_id=organizationId,
        request__actor_id=userId,
        request__source__in=(JobSource.MANUAL, JobSource.API),
        source_access_revoked_at__isnull=True,
    ).exclude(state=JobState.FINISHED)
    try:
        access = resolve_organization_access(
            actorId=userId,
            organizationId=organizationId,
            channel=AccessChannel.SESSION,
        )
    except PermissionDenied:
        # Account deletion removes membership, but JobRequest retains its source UUID.
        pass
    else:
        jobQuery = jobQuery.exclude(
            department__in=get_authorized_departments(
                access, requiredRole=DepartmentRole.OPERATOR
            )
        )
    currentTime = timezone.now()
    for job in jobQuery.select_related("request"):
        _revoke_source_job(job, currentTime)


def _get_candidates(job: Job) -> list[Executor]:
    executorQuery = Executor.objects.filter(
        department_id=job.department_id, deleted_at__isnull=True
    )
    if job.target_executor_id:
        return list(executorQuery.filter(pk=job.target_executor_id))
    if not ExecutorGroup.objects.filter(
        pk=job.target_group_id, department_id=job.department_id, deleted_at__isnull=True
    ).exists():
        return []
    return list(
        executorQuery.filter(group_memberships__group_id=job.target_group_id).order_by(
            "group_memberships__joined_at", "group_memberships__id", "id"
        )
    )


def _get_live_candidates(
    job: Job, currentTime: datetime
) -> tuple[
    list[Executor], dict[uuid.UUID, ExecutorSession], dict[uuid.UUID, ExecutorWorkState]
]:
    listCandidate = _get_candidates(job)
    dictSession = get_current_executor_sessions(
        job.request.organization_id,
        executorIds=[executor.id for executor in listCandidate],
        currentTime=currentTime,
    )
    if job.target_executor_id:
        dictSession = {
            executorId: session
            for executorId, session in dictSession.items()
            if session.id == job.target_session_id
        }
    dictWork = {
        entry.executor_id: entry
        for entry in ExecutorWorkState.objects.filter(executor_id__in=dictSession)
    }
    return listCandidate, dictSession, dictWork


def _is_busy(
    executorId: uuid.UUID,
    work: ExecutorWorkState | None,
    *,
    excludeAssignmentId: uuid.UUID | None = None,
) -> bool:
    if (
        work is None
        or work.running_run_ids
        or work.local_waiting_count
        or work.local_running_count
    ):
        return True
    assignmentQuery = Assignment.objects.filter(
        executor_id=executorId,
        session_id=work.session_id,
        state__in=_ACTIVE_ASSIGNMENT_STATES,
        job__closed_at__isnull=True,
    )
    if excludeAssignmentId:
        assignmentQuery = assignmentQuery.exclude(pk=excludeAssignmentId)
    return assignmentQuery.exists()


def _advance_job(
    job: Job,
    currentTime: datetime,
    control: DispatchControl,
    *,
    sourceDepartmentIdsByActor: dict[uuid.UUID, set[uuid.UUID]],
) -> None:
    if job.state not in (JobState.WAITING, JobState.RETRY):
        return
    if not _has_source_access(job, sourceDepartmentIdsByActor=sourceDepartmentIdsByActor):
        _revoke_source_job(job, currentTime)
        return
    if job.retry_at and job.retry_at > currentTime:
        return
    listCandidate, dictSession, dictWork = _get_live_candidates(job, currentTime)
    if not dictSession:
        _finish_job(
            job,
            "The original target association or group eligibility is no longer available.",
            notify=True,
        )
        return
    listEnabled = [
        entry
        for entry in listCandidate
        if entry.id in dictSession and entry.dispatch_enabled
    ]
    if not listEnabled:
        strReason = "Console Dispatch is paused."
        if job.reason != strReason:
            job.reason = strReason
            job.save(update_fields=["reason"])
        return
    listOnline = [
        entry
        for entry in listEnabled
        if get_executor_association_status(dictSession[entry.id], currentTime=currentTime)
        == ExecutorAssociationStatus.ONLINE
    ]
    listReady = [
        entry
        for entry in listOnline
        if entry.id in dictWork
        and dictWork[entry.id].session_id == dictSession[entry.id].id
        and dictWork[entry.id].reported_at >= control.cycle_started_at
        and dictWork[entry.id].reported_at
        >= currentTime - timedelta(seconds=_INT_WORK_STATE_STALE_SECONDS)
    ]
    if not listReady:
        if control.recovery_until and currentTime < control.recovery_until:
            return
        if not listOnline:
            _finish_job(job, "All eligible targets are confirmed offline.", notify=True)
        else:
            strReason = "Waiting for the Executor to report its current work state."
            if job.reason != strReason:
                job.reason = strReason
                job.save(update_fields=["reason"])
        return
    setFailedExecutorId = set(
        Assignment.objects.filter(
            job=job, attempt=job.attempts + 1, state=AssignmentState.FINISHED
        ).values_list("executor_id", flat=True)
    )
    listReady = [entry for entry in listReady if entry.id not in setFailedExecutorId]
    if not listReady:
        _finish_job(
            job, "Package preparation failed on all eligible online targets.", notify=True
        )
        return
    listIdle = [
        entry for entry in listReady if not _is_busy(entry.id, dictWork[entry.id])
    ]
    strPolicy = job.run_snapshot["run_conflict_policy"]
    if not listIdle and strPolicy == "skip":
        _finish_job(job, "Skipped because all eligible targets are busy.")
        return
    if not listIdle and strPolicy == "wait":
        strReason = (
            "Waiting for an eligible Executor to finish running or locally waiting work."
        )
        if (
            job.state != JobState.WAITING
            or job.reason != strReason
            or job.retry_at is not None
        ):
            job.state = JobState.WAITING
            job.reason = strReason
            job.retry_at = None
            job.save(update_fields=["state", "reason", "retry_at"])
        return
    listReady = listIdle or listReady
    dictCandidatePosition = {
        entry.id: intIndex for intIndex, entry in enumerate(listCandidate)
    }
    listReady.sort(
        key=lambda entry: (
            dictWork[entry.id].last_assigned_at is not None,
            dictWork[entry.id].last_assigned_at or currentTime,
            dictCandidatePosition[entry.id],
            str(entry.id),
        )
    )
    executor = listReady[0]
    session = dictSession[executor.id]
    Assignment.objects.create(
        job=job,
        executor=executor,
        session_id=session.id,
        actor_id=session.user_id,
        actor_name=str(session.user)[:INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH],
        computer=session.computer,
        executor_name=executor.name,
        attempt=job.attempts + 1,
    )
    ExecutorWorkState.objects.filter(pk=executor.id).update(last_assigned_at=currentTime)
    job.state = JobState.PREPARING
    job.reason = ""
    job.retry_at = None
    job.save(update_fields=["state", "reason", "retry_at"])
    notify_executor_control(executor.id)


def _reconcile_assignment(
    assignment: Assignment,
    currentTime: datetime,
    control: DispatchControl,
    *,
    sourceDepartmentIdsByActor: dict[uuid.UUID, set[uuid.UUID]],
) -> None:
    job = assignment.job
    if not _has_source_access(job, sourceDepartmentIdsByActor=sourceDepartmentIdsByActor):
        _revoke_source_job(job, currentTime)
        if assignment.state == AssignmentState.PREPARING:
            return
    if (
        assignment.state == AssignmentState.PERMITTED
        and assignment.permit_expires_at
        and assignment.permit_expires_at <= currentTime
    ):
        assignment.state = AssignmentState.REVIEW
        assignment.reason = (
            "The start permission expired without confirmed start or non-start evidence."
        )
        assignment.save(update_fields=["state", "reason"])
        notify_executor_control(assignment.executor_id)
        if job.closed_at is None:
            job.state = JobState.REVIEW
            job.reason = assignment.reason
            job.save(update_fields=["state", "reason"])
        return
    dictSession = get_current_executor_sessions(
        job.request.organization_id,
        executorIds=[assignment.executor_id],
        currentTime=currentTime,
    )
    session = dictSession.get(assignment.executor_id)
    boolSessionValid = session is not None and session.id == assignment.session_id
    boolOnline = (
        boolSessionValid
        and get_executor_association_status(session, currentTime=currentTime)
        == ExecutorAssociationStatus.ONLINE
    )
    boolRecovering = (
        control.recovery_until is not None and currentTime < control.recovery_until
    )
    boolGroupMemberValid = (
        not job.target_group_id
        or ExecutorGroupMember.objects.filter(
            group_id=job.target_group_id,
            executor_id=assignment.executor_id,
            group__deleted_at__isnull=True,
        ).exists()
    )
    if assignment.state == AssignmentState.PREPARING and (
        not boolSessionValid
        or not boolGroupMemberValid
        or (not boolOnline and not boolRecovering)
    ):
        assignment.state = AssignmentState.WITHDRAWN
        assignment.reason = "The target is no longer eligible before permission."
        assignment.save(update_fields=["state", "reason"])
        notify_executor_control(assignment.executor_id)
        job.state = JobState.WAITING
        job.save(update_fields=["state"])
    elif assignment.state in (AssignmentState.RUNNING, AssignmentState.PERMITTED) and (
        not boolSessionValid or (not boolOnline and not boolRecovering)
    ):
        assignment.state = AssignmentState.REVIEW
        assignment.reason = (
            "The original client is unavailable; actual execution remains unconfirmed."
        )
        assignment.save(update_fields=["state", "reason"])
        notify_executor_control(assignment.executor_id)
        if job.closed_at is None:
            job.state = JobState.REVIEW
            job.reason = assignment.reason
            job.save(update_fields=["state", "reason"])


@transaction.atomic
def dispatch_organization(organizationId: uuid.UUID) -> None:
    organization = Organization.objects.select_for_update().get(pk=organizationId)
    try:
        require_organization_business_available(organization)
        currentTime = timezone.now()
        control = require_control_service(currentTime)
    except (PermissionDenied, ValidationError):
        return
    # Membership and department writes take the same organization lock; never reuse these facts after commit.
    dictSourceDepartmentIdsByActor: dict[uuid.UUID, set[uuid.UUID]] = {}
    for assignment in Assignment.objects.filter(
        job__request__organization=organization, state__in=_ACTIVE_ASSIGNMENT_STATES
    ).select_related("job__request"):
        _reconcile_assignment(
            assignment,
            currentTime,
            control,
            sourceDepartmentIdsByActor=dictSourceDepartmentIdsByActor,
        )
    for job in (
        Job.objects
        .filter(
            request__organization=organization,
            state__in=(JobState.WAITING, JobState.RETRY),
        )
        .select_related("request")
        .order_by("priority", "attempt_queued_at", "id")
    ):
        _advance_job(
            job,
            currentTime,
            control,
            sourceDepartmentIdsByActor=dictSourceDepartmentIdsByActor,
        )


def get_start_evidence_not_before(permitExpiresAt: datetime) -> datetime:
    """Use the same reported-start boundary in permits and event validation."""
    return permitExpiresAt - timedelta(
        seconds=_INT_PERMIT_SECONDS + _INT_START_EVIDENCE_TOLERANCE_SECONDS
    )


def issue_permission(session: ExecutorSession, assignmentId: uuid.UUID) -> Assignment:
    currentTime = timezone.now()
    control = require_control_service(currentTime)
    assignment = (
        Assignment.objects
        .select_for_update()
        .select_related("job__request", "executor")
        .get(pk=assignmentId, session_id=session.id, executor_id=session.executor_id)
    )
    job = assignment.job
    boolPermissionIssued = assignment.permit_expires_at is not None
    if boolPermissionIssued:
        if (
            assignment.state not in (AssignmentState.PERMITTED, AssignmentState.RUNNING)
            or currentTime >= assignment.permit_expires_at
            or job.stop_requested_at
            or job.closed_at
        ):
            raise ValidationError(
                "This start permission is no longer usable.", code="permission_expired"
            )
    elif (
        assignment.state != AssignmentState.PREPARING
        or job.state != JobState.PREPARING
        or job.stop_requested_at
        or job.closed_at
    ):
        raise ValidationError(
            "This assignment no longer permits a start.", code="assignment_closed"
        )
    if not assignment.executor.dispatch_enabled:
        raise ValidationError("Console Dispatch is paused.", code="dispatch_paused")
    if not _has_source_access(job):
        raise PermissionDenied("The initiating account no longer has run permission.")
    if (
        job.target_group_id
        and not ExecutorGroupMember.objects.filter(
            group_id=job.target_group_id,
            executor_id=assignment.executor_id,
            group__deleted_at__isnull=True,
        ).exists()
    ):
        raise ValidationError(
            "The Executor is no longer a member of the target group.",
            code="assignment_changed",
        )
    work = ExecutorWorkState.objects.filter(
        pk=session.executor_id,
        session_id=session.id,
        reported_at__gte=control.cycle_started_at,
    ).first()
    if work is None or work.reported_at < currentTime - timedelta(
        seconds=_INT_WORK_STATE_STALE_SECONDS
    ):
        raise ValidationError(
            "Report current work state before requesting start permission.",
            code="work_state_required",
        )
    if job.run_snapshot["run_conflict_policy"] != "concurrent" and _is_busy(
        assignment.executor_id, work, excludeAssignmentId=assignment.id
    ):
        if not boolPermissionIssued and job.run_snapshot["run_conflict_policy"] == "skip":
            assignment.state = AssignmentState.FINISHED
            assignment.reason = (
                "Skipped because a current local run or waiting task has priority."
            )
            assignment.save(update_fields=["state", "reason"])
            _finish_job(job, assignment.reason)
            notify_executor_control(assignment.executor_id)
            return assignment
        if not boolPermissionIssued and job.target_group_id:
            assignment.state = AssignmentState.WITHDRAWN
            assignment.reason = "Current local work takes priority; return the group Job to central waiting."
            assignment.save(update_fields=["state", "reason"])
            job.state = JobState.WAITING
            job.reason = assignment.reason
            job.save(update_fields=["state", "reason"])
            notify_executor_control(assignment.executor_id)
            return assignment
        raise ValidationError(
            "Local work has priority; start permission is not available yet.",
            code="executor_busy",
        )
    if boolPermissionIssued:
        return assignment
    from packages.preparation import record_package_preparation

    record_package_preparation(
        job.package_id,
        assignment.executor_id,
        session.id,
        job.run_snapshot["python_environment_name"],
        "ready",
    )
    assignment.permit_expires_at = currentTime + timedelta(seconds=_INT_PERMIT_SECONDS)
    assignment.state = AssignmentState.PERMITTED
    assignment.save(update_fields=["permit_expires_at", "state"])
    job.state = JobState.STARTING
    job.save(update_fields=["state"])
    notify_executor_control(assignment.executor_id)
    return assignment


def control_job(job: Job, action: str, *, run: Run | None = None) -> None:
    if job.state == JobState.FINISHED:
        return
    currentTime = timezone.now()
    if action == "close":
        if job.state != JobState.REVIEW:
            raise ValidationError(
                "Only an unconfirmed Job can be closed.", code="job_not_unconfirmed"
            )
        job.closed_at = currentTime
        job.stop_requested_at = currentTime
        job.save(update_fields=["closed_at", "stop_requested_at"])
        _finish_job(
            job,
            "Closed by an authorized user; actual execution is not confirmed stopped.",
        )
        for executorId in (
            Assignment.objects
            .filter(job=job, state__in=_ACTIVE_ASSIGNMENT_STATES)
            .values_list("executor_id", flat=True)
            .distinct()
        ):
            notify_executor_control(executorId)
        return
    if run is not None and run.ended_at is not None:
        raise ValidationError("This Run has already ended.", code="run_already_ended")
    assignmentQuery = Assignment.objects.filter(
        job=job, state__in=_ACTIVE_ASSIGNMENT_STATES
    )
    if run is not None:
        assignmentQuery = assignmentQuery.filter(pk=run.assignment_id)
    assignment = assignmentQuery.first()
    if run is not None and assignment is None:
        raise ValidationError(
            "This Run no longer has an active execution.", code="run_already_ended"
        )
    job.stop_requested_at = job.stop_requested_at or currentTime
    job.save(update_fields=["stop_requested_at"])
    if assignment is None or assignment.state == AssignmentState.PREPARING:
        if assignment:
            assignment.state = AssignmentState.WITHDRAWN
            assignment.stop_requested_at = currentTime
            assignment.save(update_fields=["state", "stop_requested_at"])
        _finish_job(
            job, "Canceled before start permission; remaining retries are canceled."
        )
    else:
        assignment.stop_requested_at = assignment.stop_requested_at or currentTime
        assignment.save(update_fields=["stop_requested_at"])
        job.state = (
            JobState.REVIEW
            if assignment.state == AssignmentState.REVIEW
            else JobState.STOPPING
        )
        job.reason = "Stop requested; waiting for actual execution facts."
        job.save(update_fields=["state", "reason"])
    if assignment is not None:
        notify_executor_control(assignment.executor_id)


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
                if boolRunRetryable and _has_source_access(job):
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
                    _finish_job(job, strReason)
        elif event.kind == RunEventKind.STARTED and run.ended_at is None:
            assignment.state = AssignmentState.RUNNING
            assignment.save(update_fields=["state"])
            if job.closed_at is None:
                job.state = (
                    JobState.STOPPING if job.stop_requested_at else JobState.RUNNING
                )
                job.reason = (
                    _STR_SOURCE_ACCESS_REVOKED_REASON
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
                _finish_job(job, assignment.reason, notify=True)
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
                    _finish_job(job, "Canceled before process creation.")
                elif not _has_source_access(job):
                    _finish_job(
                        job,
                        "The source account no longer has permission to run this Job.",
                        notify=True,
                    )
                elif strPolicy == RunConflictPolicy.SKIP:
                    _finish_job(job, assignment.reason)
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
                _finish_job(job, assignment.reason, notify=job.stop_requested_at is None)
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


def run_control_tick() -> None:
    DispatchControl.objects.filter(pk=1).update(last_tick_at=timezone.now())
    listOrganizationId = list(
        Job.objects
        .exclude(state=JobState.FINISHED)
        .values_list("request__organization_id", flat=True)
        .distinct()
    )
    for organizationId in listOrganizationId:
        dispatch_organization(organizationId)


def reconcile_revoked_sessions(sessionIds: list[uuid.UUID]) -> None:
    """Close unpermitted direct work and preserve real or possible execution under the caller's organization lock."""
    if not sessionIds:
        return
    setExecutorId = set(
        ExecutorWorkState.objects.filter(session_id__in=sessionIds).values_list(
            "executor_id", flat=True
        )
    )
    currentTime = timezone.now()
    for assignment in Assignment.objects.filter(
        session_id__in=sessionIds, state__in=_ACTIVE_ASSIGNMENT_STATES
    ).select_related("job__request"):
        setExecutorId.add(assignment.executor_id)
        job = assignment.job
        if assignment.state == AssignmentState.PREPARING:
            assignment.state = AssignmentState.WITHDRAWN
            assignment.reason = (
                "The original Executor association was revoked before start permission."
            )
            assignment.save(update_fields=["state", "reason"])
            if job.state == JobState.FINISHED:
                continue
            if job.target_group_id:
                job.state = JobState.WAITING
                job.reason = "The previous group member is unavailable; another eligible member may be selected."
                job.save(update_fields=["state", "reason"])
            else:
                _finish_job(job, assignment.reason)
        else:
            assignment.state = AssignmentState.REVIEW
            assignment.reason = "The original Executor association was revoked; execution is not confirmed stopped."
            assignment.save(update_fields=["state", "reason"])
            if job.state != JobState.FINISHED:
                job.state = JobState.REVIEW
                job.reason = assignment.reason
                job.stop_requested_at = job.stop_requested_at or currentTime
                job.save(update_fields=["state", "reason", "stop_requested_at"])
    for job in Job.objects.filter(
        target_session_id__in=sessionIds, state__in=(JobState.WAITING, JobState.RETRY)
    ).select_related("request"):
        _finish_job(
            job,
            "The original Executor association was revoked; remaining work is canceled.",
        )
    for executorId in setExecutorId:
        notify_executor_control(executorId)
