# FileName: admission.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import uuid
from datetime import datetime
from typing import cast

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from accounts.models import User
from console_project.config import LimitsConfig
from console_project.constants import INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH

from organizations.models import Organization, Department, DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    require_organization_business_available,
    resolve_organization_access,
    get_authorized_departments,
)
from executors.contracts import ExecutorAssociationStatus
from executors.models import Executor, ExecutorGroup
from executors.session_state import (
    get_executor_association_status,
    get_current_executor_sessions,
)

from operations.models import AuditChannel
from operations.audit import record_audit

from .models import JobSource, JobState, JobRequest, Job, JobAdmissionBudget
from .dispatch_control import require_control_service

_DICT_PRIORITY = {"high": 0, "normal": 1, "low": 2}


def _get_request_fingerprint(content: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            content, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def get_existing_request(
    access: OrganizationAccessContext,
    *,
    source: JobSource,
    clientRequestId: uuid.UUID,
    requestContent: dict,
) -> JobRequest | None:
    """Return an authenticated receipt before parsing defaults that may have changed after admission."""
    previous = JobRequest.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        source=source,
        client_request_id=clientRequestId,
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
    if previous.request_sha256 != _get_request_fingerprint(requestContent):
        raise ValidationError(
            "This request ID was already used with different inputs.",
            code="request_conflict",
        )
    return previous


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


def accept_request(
    *,
    organizationId: uuid.UUID,
    departmentId: uuid.UUID,
    packageId: uuid.UUID,
    settings: dict | None,
    executorIds: list[uuid.UUID],
    groupId: uuid.UUID | None,
    source: JobSource,
    actorId: uuid.UUID | None,
    clientRequestId: uuid.UUID,
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
        strActorName = str(actor)[:INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH]
    strFingerprint = _get_request_fingerprint(
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
        client_request_id=clientRequestId,
    ).first()
    if previous:
        if previous.request_sha256 != strFingerprint:
            raise ValidationError(
                "This request ID was already used with different inputs.",
                code="request_conflict",
            )
        return previous
    currentTime = timezone.now()
    require_control_service(currentTime)
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
        client_request_id=clientRequestId,
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
            version=dictSnapshot["project_version"],
            target_executor_id=None if group else target.id,
            target_group_id=target.id if group else None,
            target_name=target.name,
            target_session_id=None if group else dictSession[target.id].id,
            run_snapshot=dictSnapshot,
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
