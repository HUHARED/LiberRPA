# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from operations.audit import get_audit_snapshot, record_audit
from organizations.models import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .access import require_executor_management
from .models import Executor, ExecutorGroupMember, ExecutorSession
from runs.models import Assignment, AssignmentState, Job, JobState
from schedules.models import Schedule

# NOTE: Call these writes with freshly locked Session access inside the caller's transaction.


def _get_executor_for_management(
    access: OrganizationAccessContext, executorId: uuid.UUID
) -> Executor:
    # Check visibility before reporting a role failure; foreign and hidden IDs remain unavailable.
    executor = Executor.objects.get(
        pk=executorId,
        deleted_at__isnull=True,
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
    )
    require_executor_management(access, executor.department_id)
    return executor


@sensitive_variables()
def create_executor(
    access: OrganizationAccessContext,
    *,
    departmentId: uuid.UUID,
    name: str,
    notes: str,
) -> Executor:
    """Create a logical record without assigning an account or creating a machine credential."""
    department = get_authorized_departments(
        access, requiredRole=DepartmentRole.OPERATOR
    ).get(pk=departmentId)
    require_executor_management(access, department.id)
    executor = Executor(department=department, name=name.strip(), notes=notes)
    executor.full_clean()
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    # Paused and unassociated records consume capacity; deleted identities do not.
    if (
        Executor.objects.filter(
            department__organization=access.organization, deleted_at__isnull=True
        ).count()
        >= limits.maxExecutorsPerOrganization
    ):
        raise ValidationError(
            "This organization has reached its limit of %(limit)s executors.",
            code="executor_count_limit",
            params={"limit": limits.maxExecutorsPerOrganization},
        )
    executor.save(force_insert=True)
    record_audit(
        "executor.create",
        actor=access.actor,
        organization=access.organization,
        target=executor,
        channel=access.channel,
        before={},
    )
    return executor


@sensitive_variables()
def update_executor(
    access: OrganizationAccessContext,
    *,
    executorId: uuid.UUID,
    name: str,
    notes: str,
) -> Executor:
    """Save Name and Notes; department, identity, and dispatch state stay server-controlled."""
    executor = _get_executor_for_management(access, executorId)
    dictAuditBefore = get_audit_snapshot(executor)
    executor.name = name.strip()
    executor.notes = notes
    executor.full_clean()
    executor.save(update_fields=["name", "notes"])
    record_audit(
        "executor.update",
        actor=access.actor,
        organization=access.organization,
        target=executor,
        channel=access.channel,
        before=dictAuditBefore,
    )
    return executor


@sensitive_variables()
def set_executor_dispatch(
    access: OrganizationAccessContext,
    *,
    executorId: uuid.UUID,
    dispatchEnabled: bool,
) -> Executor:
    """Set the persistent dispatch switch explicitly; repeating a request never toggles it."""
    executor = _get_executor_for_management(access, executorId)
    dictAuditBefore = get_audit_snapshot(executor)
    executor.dispatch_enabled = dispatchEnabled
    executor.save(update_fields=["dispatch_enabled"])
    record_audit(
        "executor.set_dispatch",
        actor=access.actor,
        organization=access.organization,
        target=executor,
        channel=access.channel,
        before=dictAuditBefore,
    )
    # The shared permit service checks this switch without changing accepted Waiting Jobs.
    return executor


@sensitive_variables()
def delete_executor(
    access: OrganizationAccessContext,
    *,
    executorId: uuid.UUID,
) -> Executor:
    """Remove a current record while retaining its identity for future historical references."""
    executor = _get_executor_for_management(access, executorId)
    if ExecutorGroupMember.objects.filter(
        executor=executor, group__deleted_at__isnull=True
    ).exists():
        raise ValidationError(
            "Remove this Executor from its groups before deleting it.",
            code="executor_group_reference",
        )
    if (
        Schedule.objects.filter(
            deleted_at__isnull=True, executor_ids__contains=[str(executor.pk)]
        ).exists()
        or Job.objects
        .filter(target_executor_id=executor.pk)
        .exclude(state=JobState.FINISHED)
        .exists()
        or Assignment.objects
        .filter(
            executor=executor,
            state__in=[
                AssignmentState.PREPARING,
                AssignmentState.PERMITTED,
                AssignmentState.RUNNING,
                AssignmentState.REVIEW,
            ],
        )
        .exclude(job__state=JobState.FINISHED)
        .exists()
    ):
        raise ValidationError(
            "Remove referencing Schedules and resolve unfinished work before deleting this Executor.",
            code="executor_work_reference",
        )
    # Reference creation must share this organization lock; retained history must not block deletion.
    ExecutorSession.objects.filter(executor=executor).delete()
    executor.deleted_at = timezone.now()
    executor.save(update_fields=["deleted_at"])
    record_audit(
        "executor.delete",
        actor=access.actor,
        organization=access.organization,
        target=executor,
        channel=access.channel,
    )
    return executor


@sensitive_variables()
def unassociate_executor(
    access: OrganizationAccessContext,
    *,
    executorId: uuid.UUID,
    expectedSessionId: uuid.UUID,
) -> Executor:
    """Revoke the selected association without letting a delayed retry remove a replacement."""
    executor = _get_executor_for_management(access, executorId)
    session = ExecutorSession.objects.filter(executor=executor).first()
    if session is not None:
        if session.id != expectedSessionId:
            raise ValidationError(
                "The Executor association has changed. Refresh before trying again.",
                code="executor_association_changed",
            )
        record_audit(
            "executor.unassociate",
            actor=access.actor,
            organization=access.organization,
            target=executor,
            channel=access.channel,
        )
        sessionId = session.pk
        session.delete()
        from runs.services import reconcile_revoked_sessions

        reconcile_revoked_sessions([sessionId])
    return executor
