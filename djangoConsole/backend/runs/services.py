# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import cast

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from console_project.config import LimitsConfig
from console_project.constants import INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH
from console_project.validators import validate_json_value
from executors.contracts import ExecutorAssociationStatus
from executors.models import Executor, ExecutorGroup, ExecutorGroupMember, ExecutorSession
from executors.session_state import (
    get_current_executor_sessions,
    get_executor_association_status,
)
from operations.audit import record_audit
from operations.models import AuditChannel
from organizations.models import Department, DepartmentRole, Organization
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
    require_organization_business_available,
    resolve_organization_access,
)

from .contracts import WorkEvent
from .control_notifications import notify_executor_control
from .models import (
    Assignment,
    AssignmentState,
    DispatchControl,
    ExecutorWorkState,
    Job,
    JobAdmissionBudget,
    JobRequest,
    JobSource,
    JobState,
    OutputsStatus,
    Run,
    RunEvent,
    RunEventKind,
    RunResult,
)

_INT_PERMIT_SECONDS = 15
_INT_RETRY_SECONDS = 60
_INT_CONTROL_STALE_SECONDS = 15
_INT_WORK_STATE_STALE_SECONDS = 45
_INT_CUSTOM_ARGS_BYTES = 64 * 1024
_DICT_PRIORITY = {"high": 0, "normal": 1, "low": 2}
_ACTIVE_ASSIGNMENT_STATES = (
    AssignmentState.PREPARING,
    AssignmentState.PERMITTED,
    AssignmentState.RUNNING,
    AssignmentState.REVIEW,
)


def _get_actor_name(actor: User) -> str:
    return f"{actor.username} ({actor.email})"[:INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH]


def _has_source_access(job: Job) -> bool:
    if job.request.source == JobSource.SCHEDULE:
        return True
    if job.request.actor_id is None:
        return False
    try:
        access = resolve_organization_access(
            actorId=job.request.actor_id,
            organizationId=job.request.organization_id,
            channel=AccessChannel.SESSION,
        )
        return (
            get_authorized_departments(access, requiredRole=DepartmentRole.OPERATOR)
            .filter(pk=job.department_id)
            .exists()
        )
    except PermissionDenied:
        return False


def _finish_job(job: Job, reason: str, *, notify: bool = False) -> None:
    job.state = JobState.FINISHED
    job.reason = reason[:2000]
    job.ended_at = timezone.now()
    job.retry_at = None
    job.save(update_fields=["state", "reason", "ended_at", "retry_at"])
    if notify:
        from notifications.run_events import notify_job_failure

        notify_job_failure(job)


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


def _require_control_service(currentTime: datetime) -> DispatchControl:
    control = DispatchControl.objects.filter(pk=1).first()
    if control is None or control.last_tick_at < currentTime - timedelta(
        seconds=_INT_CONTROL_STALE_SECONDS
    ):
        raise ValidationError(
            "The run control worker is unavailable.", code="control_service_unavailable"
        )
    return control


def _consume_admission_budget(
    organizationId: uuid.UUID, count: int, currentTime: datetime
) -> None:
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if (
        Job.objects
        .filter(request__organization_id=organizationId)
        .exclude(state=JobState.FINISHED)
        .count()
        + count
        > limits.maxActiveJobsPerOrganization
    ):
        raise ValidationError(
            "The organization has reached its active Job limit.", code="active_job_limit"
        )
    budget, boolCreated = JobAdmissionBudget.objects.get_or_create(
        organization_id=organizationId,
        defaults={"tokens": float(limits.newJobsBurst), "updated_at": currentTime},
    )
    floatTokens = min(
        float(limits.newJobsBurst),
        budget.tokens
        + max(0, (currentTime - budget.updated_at).total_seconds())
        * limits.newJobsPerMinute
        / 60,
    )
    if floatTokens < count:
        raise ValidationError(
            "The organization has reached its new Job rate limit.",
            code="new_job_rate_limit",
        )
    budget.tokens = floatTokens - count
    budget.updated_at = currentTime
    budget.save(update_fields=["tokens", "updated_at"])


def get_request_fingerprint(content: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            content, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def get_existing_request(
    access: OrganizationAccessContext,
    *,
    source: JobSource,
    requestId: uuid.UUID,
    requestContent: dict,
) -> JobRequest | None:
    """Return an authenticated receipt before parsing defaults that may have changed after admission."""
    previous = JobRequest.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        source=source,
        request_id=requestId,
    ).first()
    if previous is None:
        return None
    if (
        not get_authorized_departments(access, requiredRole=DepartmentRole.OPERATOR)
        .filter(pk=previous.department_id)
        .exists()
    ):
        raise PermissionDenied(
            "Current department access is required to read the original request."
        )
    if previous.request_sha256 != get_request_fingerprint(requestContent):
        raise ValidationError(
            "This request ID was already used with different inputs.",
            code="request_conflict",
        )
    return previous


def accept_request(
    *,
    organizationId: uuid.UUID,
    departmentId: uuid.UUID,
    packageId: uuid.UUID,
    settings: dict | None,
    executorIds: list[uuid.UUID],
    groupId: uuid.UUID | None,
    source: str,
    actorId: uuid.UUID | None,
    requestId: uuid.UUID,
    scheduleId: uuid.UUID | None = None,
    scheduleName: str = "",
    scheduledAt: datetime | None = None,
    requestContent: dict | None = None,
) -> JobRequest:
    """Accept all targets together under the caller's organization lock and transaction."""
    from packages.models import Package
    from packages.runtime import get_run_snapshot

    if bool(executorIds) == (groupId is not None) or len(set(executorIds)) != len(
        executorIds
    ):
        raise ValidationError(
            "Select unique Executors or one group.", code="invalid_job_targets"
        )
    jobSource = JobSource(source)
    organization = Organization.objects.get(pk=organizationId)
    require_organization_business_available(organization)
    department = Department.objects.get(
        pk=departmentId, organization=organization, deleted_at__isnull=True
    )
    actor: User | None = None
    strActorName = "System"
    if jobSource != JobSource.SCHEDULE:
        if actorId is None:
            raise PermissionDenied("A source account is required.")
        access = resolve_organization_access(
            actorId=actorId, organizationId=organizationId, channel=AccessChannel.SESSION
        )
        if (
            not get_authorized_departments(access, requiredRole=DepartmentRole.OPERATOR)
            .filter(pk=departmentId)
            .exists()
        ):
            raise PermissionDenied("Operator access is required to run a package.")
        actor = access.actor
        strActorName = _get_actor_name(actor)
    strFingerprint = get_request_fingerprint(
        requestContent
        if requestContent is not None
        else {
            "package_id": str(packageId),
            "settings": settings,
            "executor_ids": [str(entry) for entry in executorIds],
            "group_id": str(groupId) if groupId else None,
            "source": str(jobSource),
            "actor_id": str(actorId) if actorId else None,
            "schedule_id": str(scheduleId) if scheduleId else None,
            "scheduled_at": scheduledAt.isoformat() if scheduledAt else None,
        }
    )
    previous = JobRequest.objects.filter(
        organization_id=organizationId,
        actor_id=actorId,
        source=jobSource,
        request_id=requestId,
    ).first()
    if previous:
        if previous.request_sha256 != strFingerprint:
            raise ValidationError(
                "This request ID was already used with different inputs.",
                code="request_conflict",
            )
        return previous
    currentTime = timezone.now()
    _require_control_service(currentTime)
    package = Package.objects.select_related("blob").get(
        pk=packageId, department=department
    )
    dictSnapshot = get_run_snapshot(
        package, settingsOverride=settings, departmentId=departmentId
    )
    if groupId:
        group = ExecutorGroup.objects.get(
            pk=groupId, department=department, deleted_at__isnull=True
        )
        listExecutor = list(
            Executor.objects.filter(
                group_memberships__group=group,
                deleted_at__isnull=True,
                department=department,
            )
        )
        if not listExecutor:
            raise ValidationError(
                "The group has no eligible members.", code="no_eligible_target"
            )
    else:
        group = None
        listExecutor = list(
            Executor.objects.filter(
                pk__in=executorIds, department=department, deleted_at__isnull=True
            )
        )
        if len(listExecutor) != len(executorIds):
            raise ValidationError(
                "Every target must belong to the package department.",
                code="invalid_job_targets",
            )
    dictSession = get_current_executor_sessions(
        organizationId,
        executorIds=[entry.id for entry in listExecutor],
        currentTime=currentTime,
    )
    listAssociated = [entry for entry in listExecutor if entry.id in dictSession]
    if listAssociated and all(not entry.dispatch_enabled for entry in listAssociated):
        raise ValidationError(
            "Console Dispatch is paused on every eligible target.", code="target_paused"
        )
    listAvailable = [
        entry
        for entry in listExecutor
        if entry.dispatch_enabled
        and entry.id in dictSession
        and get_executor_association_status(
            dictSession[entry.id], currentTime=currentTime
        )
        == ExecutorAssociationStatus.ONLINE
    ]
    if not listAvailable or (group is None and len(listAvailable) != len(listExecutor)):
        raise ValidationError(
            "A target is offline, unassociated, unauthorized, or dispatch is paused.",
            code="target_unavailable",
        )
    intCount = 1 if group else len(listExecutor)
    _consume_admission_budget(organizationId, intCount, currentTime)
    jobRequest = JobRequest.objects.create(
        organization=organization,
        department=department,
        request_id=requestId,
        actor_id=actorId,
        actor_name=strActorName,
        source=jobSource,
        request_sha256=strFingerprint,
        schedule_id=scheduleId,
        schedule_name=scheduleName,
        scheduled_at=scheduledAt,
        accepted_at=currentTime,
    )
    listTarget: list[Executor | ExecutorGroup] = [group] if group else [*listExecutor]
    for target in listTarget:
        Job.objects.create(
            request=jobRequest,
            department=department,
            package_id=packageId,
            project_name=dictSnapshot["project_name"],
            version=dictSnapshot["version"],
            target_executor_id=None if group else target.id,
            target_group_id=target.id if group else None,
            target_name=target.name,
            target_session_id=None if group else dictSession[target.id].id,
            inputs=dictSnapshot,
            priority=_DICT_PRIORITY[dictSnapshot["priority"]],
            retry_count=dictSnapshot["retry_count"],
            queued_at=currentTime,
            attempt_queued_at=currentTime,
        )
    record_audit(
        "job.accept",
        actor=actor,
        organization=organization,
        target=jobRequest,
        channel=AuditChannel.API_KEY
        if jobSource == JobSource.API
        else AuditChannel.SESSION,
        metadata={
            "job_count": intCount,
            "package_id": str(packageId),
            "source": str(jobSource),
        },
    )
    return jobRequest


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


def _advance_job(job: Job, currentTime: datetime, control: DispatchControl) -> None:
    if job.state not in (JobState.WAITING, JobState.RETRY):
        return
    if job.retry_at and job.retry_at > currentTime:
        return
    if not _has_source_access(job):
        _finish_job(
            job,
            "The source account no longer has permission to run this Job.",
            notify=True,
        )
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
        job.reason = "Console Dispatch is paused."
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
            job.reason = "Waiting for the Executor to report its current work state."
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
    strPolicy = job.inputs["run_conflict_policy"]
    if not listIdle and strPolicy == "skip":
        _finish_job(job, "Skipped because all eligible targets are busy.")
        return
    if not listIdle and strPolicy == "wait":
        job.state = JobState.WAITING
        job.reason = (
            "Waiting for an eligible Executor to finish running or locally waiting work."
        )
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
        actor_name=_get_actor_name(session.user),
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
    assignment: Assignment, currentTime: datetime, control: DispatchControl
) -> None:
    job = assignment.job
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
    boolSourceValid = _has_source_access(job)
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
        or not boolSourceValid
        or not boolGroupMemberValid
        or (not boolOnline and not boolRecovering)
    ):
        assignment.state = AssignmentState.WITHDRAWN
        assignment.reason = (
            "The target or source is no longer eligible before permission."
        )
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
        control = _require_control_service(currentTime)
    except (PermissionDenied, ValidationError):
        return
    for assignment in Assignment.objects.filter(
        job__request__organization=organization, state__in=_ACTIVE_ASSIGNMENT_STATES
    ).select_related("job__request"):
        _reconcile_assignment(assignment, currentTime, control)
    for job in (
        Job.objects
        .filter(
            request__organization=organization,
            state__in=(JobState.WAITING, JobState.RETRY),
        )
        .select_related("request")
        .order_by("priority", "attempt_queued_at", "id")
    ):
        _advance_job(job, currentTime, control)


def issue_permission(session: ExecutorSession, assignmentId: uuid.UUID) -> Assignment:
    currentTime = timezone.now()
    control = _require_control_service(currentTime)
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
    if job.inputs["run_conflict_policy"] != "concurrent" and _is_busy(
        assignment.executor_id, work, excludeAssignmentId=assignment.id
    ):
        if not boolPermissionIssued and job.inputs["run_conflict_policy"] == "skip":
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
            notify_executor_control(assignment.executor_id)
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
        job.inputs["python_environment_name"],
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


def _capture_outputs(run: Run, event: WorkEvent) -> None:
    run.outputs_status = event.outputs_status
    run.outputs = event.outputs
    run.outputs_reason = event.outputs_reason
    run.outputs_unavailable_keys = event.outputs_unavailable_keys
    try:
        if event.outputs_status in (OutputsStatus.COMPLETE, OutputsStatus.PARTIAL):
            if event.outputs is None:
                raise ValueError("The output object was not provided.")
            validate_json_value(event.outputs)
            if (
                len(
                    json.dumps(
                        event.outputs,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                )
                > _INT_CUSTOM_ARGS_BYTES
            ):
                raise ValueError("Outputs exceed the 64 KiB snapshot limit.")
        else:
            run.outputs = None
    except (ValueError, UnicodeError, RecursionError) as e:
        run.outputs_status = OutputsStatus.UNAVAILABLE
        run.outputs = None
        run.outputs_reason = str(e)[:2000]


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
            or startedAt
            < assignment.permit_expires_at - timedelta(seconds=_INT_PERMIT_SECONDS + 5)
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
            _capture_outputs(run, event)
            run.save()
            assignment.state = AssignmentState.FINISHED
            assignment.reason = event.reason
            assignment.save(update_fields=["state", "reason"])
            if job.closed_at is None:
                if run.result in (RunResult.COMPLETED, RunResult.ERROR):
                    notify_run_event(run, event=str(run.result))
                if (
                    run.result == RunResult.ERROR
                    and job.stop_requested_at is None
                    and assignment.attempt <= job.retry_count
                    and _has_source_access(job)
                ):
                    job.state = JobState.RETRY
                    job.retry_at = timezone.now() + timedelta(seconds=_INT_RETRY_SECONDS)
                    job.attempt_queued_at = job.retry_at
                    job.reason = "Waiting 60 seconds before the next attempt."
                    job.save(
                        update_fields=["state", "retry_at", "attempt_queued_at", "reason"]
                    )
                else:
                    _finish_job(job, event.reason or f"Run {run.result}.")
        elif event.kind == RunEventKind.STARTED and run.ended_at is None:
            assignment.state = AssignmentState.RUNNING
            assignment.save(update_fields=["state"])
            if job.closed_at is None:
                job.state = (
                    JobState.STOPPING if job.stop_requested_at else JobState.RUNNING
                )
                job.reason = ""
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
            job.inputs["python_environment_name"],
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
        assignment.state = AssignmentState.FINISHED
        assignment.reason = event.reason or "The client confirmed no process was created."
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
    if boolWasPreparing and assignment.state != AssignmentState.PREPARING:
        notify_executor_control(assignment.executor_id)


def start_control_cycle() -> None:
    with transaction.atomic():
        currentTime = timezone.now()
        control, _ = DispatchControl.objects.select_for_update().get_or_create(pk=1)
        control.cycle_started_at = currentTime
        control.last_tick_at = currentTime
        control.recovery_until = currentTime + timedelta(seconds=60)
        control.save()
        # Unpermitted offers can be withdrawn after restart; existing permissions must be reconciled.
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
