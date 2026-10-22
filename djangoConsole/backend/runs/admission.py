# FileName: admission.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import copy
import hashlib
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from accounts.models import User
from console_project.contracts import JsonValue
from console_project.constants import INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH

from organizations.contracts import DepartmentRole
from organizations.models import Organization
from organizations.limits import get_organization_limits
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
)
from executors.contracts import ExecutorAssociationStatus
from executors.models import Executor, ExecutorGroup
from executors.session_state import (
    get_executor_association_status,
    get_current_executor_sessions,
)

from operations.contracts import AuditAction, AuditChannel
from operations.audit import record_audit

from packages.contracts import RUN_PRIORITY_ORDER, RunSettings
from packages.models import Package
from packages.run_settings import parse_run_settings, get_run_snapshot

from .contracts import JobSource, JobState, JobCreationRequest
from .models import JobRequest, Job, JobAdmissionBudget
from operations.maintenance import require_service_normal

from .dispatch_control import require_control_service

if TYPE_CHECKING:
    from schedules.models import Schedule


def _get_request_digest(content: dict[str, JsonValue]) -> str:
    return hashlib.sha256(
        json.dumps(
            content, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def _get_existing_request(
    access: OrganizationAccessContext,
    *,
    source: JobSource,
    clientRequestId: uuid.UUID,
    requestDigest: str,
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
    if previous.request_digest != requestDigest:
        raise ValidationError(
            "This request ID was already used with different inputs.",
            code="request_conflict",
        )
    return previous


def _consume_admission_budget(
    organization: Organization, count: int, currentTime: datetime
) -> None:
    limits = get_organization_limits(organization)
    if (
        Job.objects
        .filter(request__organization=organization)
        .exclude(state=JobState.FINISHED)
        .count()
        + count
        > limits.maxActiveJobsPerOrganization
    ):
        raise ValidationError(
            "The organization has reached its active Job limit.", code="active_job_limit"
        )
    budget, boolCreated = JobAdmissionBudget.objects.get_or_create(
        organization=organization,
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


def _create_request(
    organization: Organization,
    package: Package,
    runSettings: RunSettings,
    *,
    executorIds: list[uuid.UUID],
    groupId: uuid.UUID | None,
    source: JobSource,
    actorId: uuid.UUID | None,
    actor: User | None,
    clientRequestId: uuid.UUID,
    requestDigest: str,
    scheduleId: uuid.UUID | None = None,
    scheduleName: str = "",
    scheduledAt: datetime | None = None,
) -> JobRequest:
    """Create a new request under the caller's organization lock after receipt and access checks."""
    department = package.department
    currentTime = timezone.now()
    require_control_service(currentTime)
    require_service_normal()
    dictSnapshot = get_run_snapshot(package, runSettings)
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
        organization.pk,
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
    _consume_admission_budget(organization, intCount, currentTime)
    jobRequest = JobRequest.objects.create(
        organization=organization,
        department=department,
        client_request_id=clientRequestId,
        actor_id=actorId,
        actor_name=str(actor)[:INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH]
        if actor
        else "System",
        source=source,
        request_digest=requestDigest,
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
            package_id=package.pk,
            project_name=package.project_name,
            project_version=package.project_version,
            target_executor_id=None if group else target.id,
            target_group_id=target.id if group else None,
            target_name=target.name,
            target_session_id=None if group else dictSession[target.id].id,
            run_snapshot=dictSnapshot,
            priority_rank=RUN_PRIORITY_ORDER.index(runSettings.priority),
            max_retry_count=runSettings.max_retry_count,
            queued_at=currentTime,
            attempt_queued_at=currentTime,
        )
    record_audit(
        AuditAction.JOB_ACCEPT,
        actor=actor,
        organization=organization,
        target=jobRequest,
        channel=AuditChannel.API_KEY if source == JobSource.API else AuditChannel.SESSION,
        metadata={
            "job_count": intCount,
            "package_id": str(package.pk),
            "source": str(source),
        },
    )
    return jobRequest


def accept_request(
    access: OrganizationAccessContext, payload: JobCreationRequest
) -> tuple[JobRequest, bool]:
    """Return the original receipt or create one request within the caller's locked transaction."""

    def get_request_settings(package: Package) -> RunSettings:
        dictOverrideSettings = dict(payload.settings or {})
        if not dictOverrideSettings.keys() <= RunSettings.model_fields.keys():
            raise ValidationError({
                "settings": "One or more settings cannot be overridden for a single run."
            })
        if access.channel == AccessChannel.API_KEY:
            if any(
                strField in dictOverrideSettings
                for strField in ("custom_prj_args", "custom_arg_assets")
            ):
                raise ValidationError({
                    "settings": (
                        "Use custom_args for API inputs; argument lists and bindings cannot be overridden."
                    )
                })
            dictOverride = payload.custom_args or {}
            if not dictOverride.keys() <= set(package.api_input_keys):
                raise ValidationError({
                    "custom_args": "One or more input names are not enabled for API overrides."
                })
            if dictOverride:
                listArgument = copy.deepcopy(package.custom_prj_args)
                listBinding: list[JsonValue] = copy.deepcopy(
                    package.custom_arg_assets
                ) or [None] * len(listArgument)
                dictPosition = {
                    entry[0]: intIndex for intIndex, entry in enumerate(listArgument)
                }
                for strName, value in dictOverride.items():
                    if strName not in dictPosition:
                        raise ValidationError({
                            "custom_args": "An API input name is no longer present in the Package."
                        })
                    intIndex = dictPosition[strName]
                    listArgument[intIndex][1] = value
                    listBinding[intIndex] = None
                dictOverrideSettings["custom_prj_args"] = listArgument
                dictOverrideSettings["custom_arg_assets"] = listBinding
        elif payload.custom_args is not None:
            raise ValidationError({"custom_args": "Use run settings for a web request."})
        return parse_run_settings(package, overrides=dictOverrideSettings)

    source = (
        JobSource.API if access.channel == AccessChannel.API_KEY else JobSource.MANUAL
    )
    strRequestDigest = _get_request_digest(payload.model_dump(mode="json"))
    previous = _get_existing_request(
        access,
        source=source,
        clientRequestId=payload.request_id,
        requestDigest=strRequestDigest,
    )
    if previous is not None:
        return previous, False
    package = Package.objects.select_related("department").get(
        pk=payload.package_id,
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
    )
    jobRequest = _create_request(
        access.organization,
        package,
        get_request_settings(package),
        executorIds=payload.executor_ids,
        groupId=payload.group_id,
        source=source,
        actorId=access.actorId,
        actor=access.actor,
        clientRequestId=payload.request_id,
        requestDigest=strRequestDigest,
    )
    return jobRequest, True


def accept_schedule_trigger(
    organization: Organization, schedule: "Schedule", scheduledAt: datetime
) -> JobRequest:
    """Accept a new trigger after the worker has locked and checked its unique Schedule point."""
    listExecutorId = [uuid.UUID(strValue) for strValue in schedule.executor_ids]
    if bool(listExecutorId) == (schedule.group_id is not None) or len(
        set(listExecutorId)
    ) != len(listExecutorId):
        raise ValidationError({"executor_ids": "Select unique Executors or one group."})

    package = Package.objects.select_related("department").get(
        pk=schedule.package_id,
        department_id=schedule.department_id,
        department__organization=organization,
        department__deleted_at__isnull=True,
    )
    runSettings = parse_run_settings(schedule)
    # ScheduleTrigger and the organization lock already protect this point from duplicate admission.
    strRequestDigest = _get_request_digest({
        "schedule_id": str(schedule.pk),
        "scheduled_at": scheduledAt.isoformat(),
    })
    return _create_request(
        organization,
        package,
        runSettings,
        executorIds=listExecutorId,
        groupId=schedule.group_id,
        source=JobSource.SCHEDULE,
        actorId=schedule.created_by_id,
        actor=None,
        clientRequestId=uuid.uuid4(),
        requestDigest=strRequestDigest,
        scheduleId=schedule.pk,
        scheduleName=schedule.name,
        scheduledAt=scheduledAt,
    )
