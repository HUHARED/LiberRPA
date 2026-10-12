# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from organizations.models import DepartmentRole
from organizations.permissions import (
    AccessChannel,
    resolve_organization_access,
    get_authorized_departments,
)

from .contracts import (
    JobSource,
    JobState,
    AssignmentState,
    ACTIVE_ASSIGNMENT_STATES,
    JobControlAction,
)
from .models import Job, ExecutorWorkState, Assignment, Run
from .control_notifications import notify_executor_control

STR_SOURCE_ACCESS_REVOKED_REASON = (
    "The initiating account lost run permission; no further attempts will be scheduled."
)


def has_job_source_access(
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


def finish_job(job: Job, reason: str, *, notify: bool = False) -> None:
    job.state = JobState.FINISHED
    job.reason = reason[:2000]
    job.ended_at = timezone.now()
    job.retry_at = None
    job.save(update_fields=["state", "reason", "ended_at", "retry_at"])
    if notify:
        from notifications.run_events import notify_job_failure

        notify_job_failure(job)


def revoke_job_source_access(job: Job, currentTime: datetime) -> None:
    """Persist lost source authority without inventing a stop or an execution result."""
    if job.state == JobState.FINISHED or job.source_access_revoked_at is not None:
        return
    job.source_access_revoked_at = currentTime
    job.retry_at = None
    job.reason = (
        f"{job.reason[:1800]}\n{STR_SOURCE_ACCESS_REVOKED_REASON}"
        if job.reason
        else STR_SOURCE_ACCESS_REVOKED_REASON
    )
    job.save(update_fields=["source_access_revoked_at", "retry_at", "reason"])
    assignment = Assignment.objects.filter(
        job=job, state__in=ACTIVE_ASSIGNMENT_STATES
    ).first()
    if assignment is not None and assignment.state != AssignmentState.PREPARING:
        # An issued permit may already have produced a process; retain its evidence and active state.
        return
    if assignment is not None:
        assignment.state = AssignmentState.WITHDRAWN
        assignment.reason = STR_SOURCE_ACCESS_REVOKED_REASON
        assignment.stop_requested_at = assignment.stop_requested_at or currentTime
        assignment.save(update_fields=["state", "reason", "stop_requested_at"])
        notify_executor_control(assignment.executor_id)
    finish_job(job, STR_SOURCE_ACCESS_REVOKED_REASON, notify=True)


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
        revoke_job_source_access(job, currentTime)


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
        session_id__in=sessionIds, state__in=ACTIVE_ASSIGNMENT_STATES
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
                finish_job(job, assignment.reason)
        else:
            assignment.state = AssignmentState.NEEDS_REVIEW
            assignment.reason = "The original Executor association was revoked; execution is not confirmed stopped."
            assignment.save(update_fields=["state", "reason"])
            if job.state != JobState.FINISHED:
                job.state = JobState.NEEDS_REVIEW
                job.reason = assignment.reason
                job.stop_requested_at = job.stop_requested_at or currentTime
                job.save(update_fields=["state", "reason", "stop_requested_at"])
    for job in Job.objects.filter(
        target_session_id__in=sessionIds,
        state__in=(JobState.WAITING, JobState.WAITING_RETRY),
    ).select_related("request"):
        finish_job(
            job,
            "The original Executor association was revoked; remaining work is canceled.",
        )
    for executorId in setExecutorId:
        notify_executor_control(executorId)


def control_job(job: Job, action: JobControlAction, *, run: Run | None = None) -> None:
    if job.state == JobState.FINISHED:
        return
    currentTime = timezone.now()
    if action == JobControlAction.CLOSE:
        if job.state != JobState.NEEDS_REVIEW:
            raise ValidationError(
                "Only an unconfirmed Job can be closed.", code="job_not_unconfirmed"
            )
        job.closed_at = currentTime
        job.stop_requested_at = currentTime
        job.save(update_fields=["closed_at", "stop_requested_at"])
        finish_job(
            job,
            "Closed by an authorized user; actual execution is not confirmed stopped.",
        )
        for executorId in (
            Assignment.objects
            .filter(job=job, state__in=ACTIVE_ASSIGNMENT_STATES)
            .values_list("executor_id", flat=True)
            .distinct()
        ):
            notify_executor_control(executorId)
        return
    if run is not None and run.ended_at is not None:
        raise ValidationError("This Run has already ended.", code="run_already_ended")
    assignmentQuery = Assignment.objects.filter(
        job=job, state__in=ACTIVE_ASSIGNMENT_STATES
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
        finish_job(
            job, "Canceled before start permission; remaining retries are canceled."
        )
    else:
        assignment.stop_requested_at = assignment.stop_requested_at or currentTime
        assignment.save(update_fields=["stop_requested_at"])
        job.state = (
            JobState.NEEDS_REVIEW
            if assignment.state == AssignmentState.NEEDS_REVIEW
            else JobState.STOPPING
        )
        job.reason = "Stop requested; waiting for actual execution facts."
        job.save(update_fields=["state", "reason"])
    if assignment is not None:
        notify_executor_control(assignment.executor_id)
