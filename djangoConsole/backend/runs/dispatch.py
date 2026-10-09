# FileName: dispatch.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Iterable
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
from organizations.models import Organization
from organizations.permissions import require_organization_business_available
from packages.contracts import PackagePreparationState

from .models import (
    JobState,
    AssignmentState,
    Job,
    ExecutorWorkState,
    Assignment,
    DispatchControl,
)
from .control_notifications import notify_executor_control
from .dispatch_control import require_control_service
from .services import (
    ACTIVE_ASSIGNMENT_STATES,
    has_job_source_access,
    finish_job,
    revoke_job_source_access,
)

_INT_PERMIT_SECONDS = 15
_INT_START_EVIDENCE_TOLERANCE_SECONDS = 5
_INT_WORK_STATE_STALE_SECONDS = 45


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


def _get_dispatch_sessions(
    organizationId: uuid.UUID,
    executorIds: Iterable[uuid.UUID],
    currentTime: datetime,
    *,
    sessionsByExecutor: dict[uuid.UUID, ExecutorSession | None],
) -> dict[uuid.UUID, ExecutorSession]:
    """Reuse association checks only within the caller's locked organization dispatch pass."""
    setExecutorId = set(executorIds)
    setUnreadExecutorId = setExecutorId.difference(sessionsByExecutor)
    if setUnreadExecutorId:
        dictCurrentSession = get_current_executor_sessions(
            organizationId, executorIds=setUnreadExecutorId, currentTime=currentTime
        )
        # Remember absent and invalid associations too, but never beyond this transaction.
        for executorId in setUnreadExecutorId:
            sessionsByExecutor[executorId] = dictCurrentSession.get(executorId)
    dictSession: dict[uuid.UUID, ExecutorSession] = {}
    for executorId in setExecutorId:
        session = sessionsByExecutor[executorId]
        if session is not None:
            dictSession[executorId] = session
    return dictSession


def _get_live_candidates(
    job: Job,
    currentTime: datetime,
    *,
    candidatesByTarget: dict[
        tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None], list[Executor]
    ],
    sessionsByExecutor: dict[uuid.UUID, ExecutorSession | None],
) -> tuple[list[Executor], dict[uuid.UUID, ExecutorSession]]:
    targetKey = (job.department_id, job.target_executor_id, job.target_group_id)
    if targetKey not in candidatesByTarget:
        candidatesByTarget[targetKey] = _get_candidates(job)
    listCandidate = candidatesByTarget[targetKey]
    dictSession = _get_dispatch_sessions(
        job.request.organization_id,
        (executor.id for executor in listCandidate),
        currentTime,
        sessionsByExecutor=sessionsByExecutor,
    )
    if job.target_executor_id:
        dictSession = {
            executorId: session
            for executorId, session in dictSession.items()
            if session.id == job.target_session_id
        }
    return listCandidate, dictSession


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
        state__in=ACTIVE_ASSIGNMENT_STATES,
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
    candidatesByTarget: dict[
        tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None], list[Executor]
    ],
    sessionsByExecutor: dict[uuid.UUID, ExecutorSession | None],
) -> None:
    if job.state not in (JobState.WAITING, JobState.RETRY):
        return
    if not has_job_source_access(
        job, sourceDepartmentIdsByActor=sourceDepartmentIdsByActor
    ):
        revoke_job_source_access(job, currentTime)
        return
    if job.retry_at and job.retry_at > currentTime:
        return
    listCandidate, dictSession = _get_live_candidates(
        job,
        currentTime,
        candidatesByTarget=candidatesByTarget,
        sessionsByExecutor=sessionsByExecutor,
    )
    if not dictSession:
        finish_job(
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
    # Work reports and last_assigned_at can change during this pass; read them for each eligible Job.
    dictWork: dict[uuid.UUID, ExecutorWorkState] = {}
    if listOnline:
        dictWork = {
            entry.executor_id: entry
            for entry in ExecutorWorkState.objects.filter(
                executor_id__in=[executor.id for executor in listOnline]
            )
        }
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
            finish_job(job, "All eligible targets are confirmed offline.", notify=True)
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
        finish_job(
            job, "Package preparation failed on all eligible online targets.", notify=True
        )
        return
    listIdle = [
        entry for entry in listReady if not _is_busy(entry.id, dictWork[entry.id])
    ]
    strPolicy = job.run_snapshot["run_conflict_policy"]
    if not listIdle and strPolicy == "skip":
        finish_job(job, "Skipped because all eligible targets are busy.")
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
    session: ExecutorSession | None,
) -> None:
    job = assignment.job
    if not has_job_source_access(
        job, sourceDepartmentIdsByActor=sourceDepartmentIdsByActor
    ):
        revoke_job_source_access(job, currentTime)
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
    # Account, target and association writes take this organization lock; these lookups end at commit.
    dictSourceDepartmentIdsByActor: dict[uuid.UUID, set[uuid.UUID]] = {}
    dictSessionByExecutor: dict[uuid.UUID, ExecutorSession | None] = {}
    listAssignment = list(
        Assignment.objects.filter(
            job__request__organization=organization, state__in=ACTIVE_ASSIGNMENT_STATES
        ).select_related("job__request")
    )
    dictAssignmentSession = _get_dispatch_sessions(
        organization.id,
        (assignment.executor_id for assignment in listAssignment),
        currentTime,
        sessionsByExecutor=dictSessionByExecutor,
    )
    for assignment in listAssignment:
        _reconcile_assignment(
            assignment,
            currentTime,
            control,
            sourceDepartmentIdsByActor=dictSourceDepartmentIdsByActor,
            session=dictAssignmentSession.get(assignment.executor_id),
        )
    dictCandidateByTarget: dict[
        tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None], list[Executor]
    ] = {}
    # Reconciliation can return a Job to Waiting; query the queue only after that phase.
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
            candidatesByTarget=dictCandidateByTarget,
            sessionsByExecutor=dictSessionByExecutor,
        )


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
    if not has_job_source_access(job):
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
            finish_job(job, assignment.reason)
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
        PackagePreparationState.READY,
    )
    assignment.permit_expires_at = currentTime + timedelta(seconds=_INT_PERMIT_SECONDS)
    assignment.state = AssignmentState.PERMITTED
    assignment.save(update_fields=["permit_expires_at", "state"])
    job.state = JobState.STARTING
    job.save(update_fields=["state"])
    notify_executor_control(assignment.executor_id)
    return assignment
