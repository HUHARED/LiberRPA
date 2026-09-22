# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from organizations.models import DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
)

from .access import lock_executor_write_access, require_executor_management
from .models import Executor, ExecutorGroupMember, ExecutorSession


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
@transaction.atomic
def create_executor(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    departmentId: uuid.UUID,
    name: str,
    notes: str,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> Executor:
    """Create a logical record without assigning an account or creating a machine credential."""
    access = lock_executor_write_access(
        actorId, organizationId, channel, sessionAuthHash, sessionExpiresAt
    )
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
    return executor


@sensitive_variables()
@transaction.atomic
def update_executor(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    executorId: uuid.UUID,
    name: str,
    notes: str,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> Executor:
    """Save Name and Notes; department, identity, and dispatch state stay server-controlled."""
    access = lock_executor_write_access(
        actorId, organizationId, channel, sessionAuthHash, sessionExpiresAt
    )
    executor = _get_executor_for_management(access, executorId)
    executor.name = name.strip()
    executor.notes = notes
    executor.full_clean()
    executor.save(update_fields=["name", "notes"])
    return executor


@sensitive_variables()
@transaction.atomic
def set_executor_dispatch(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    executorId: uuid.UUID,
    dispatchEnabled: bool,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> Executor:
    """Set the persistent dispatch switch explicitly; repeating a request never toggles it."""
    access = lock_executor_write_access(
        actorId, organizationId, channel, sessionAuthHash, sessionExpiresAt
    )
    executor = _get_executor_for_management(access, executorId)
    executor.dispatch_enabled = dispatchEnabled
    executor.save(update_fields=["dispatch_enabled"])
    # TODO: New central permits must check this switch; pausing must not stop active Runs or clear Waiting Jobs.
    return executor


@sensitive_variables()
@transaction.atomic
def delete_executor(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    executorId: uuid.UUID,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> Executor:
    """Remove a current record while retaining its identity for future historical references."""
    access = lock_executor_write_access(
        actorId, organizationId, channel, sessionAuthHash, sessionExpiresAt
    )
    executor = _get_executor_for_management(access, executorId)
    if ExecutorGroupMember.objects.filter(
        executor=executor, group__deleted_at__isnull=True
    ).exists():
        raise ValidationError(
            "Remove this Executor from its groups before deleting it.",
            code="executor_group_reference",
        )
    # TODO: Check Schedule/current-work references when those models are added.
    # Reference creation must share this organization lock; retained history must not block deletion.
    ExecutorSession.objects.filter(executor=executor).delete()
    executor.deleted_at = timezone.now()
    executor.save(update_fields=["deleted_at"])
    return executor


@sensitive_variables()
@transaction.atomic
def unassociate_executor(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    executorId: uuid.UUID,
    expectedSessionId: uuid.UUID,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> Executor:
    """Revoke the selected association without letting a delayed retry remove a replacement."""
    access = lock_executor_write_access(
        actorId, organizationId, channel, sessionAuthHash, sessionExpiresAt
    )
    executor = _get_executor_for_management(access, executorId)
    session = ExecutorSession.objects.filter(executor=executor).first()
    if session is not None:
        if session.id != expectedSessionId:
            raise ValidationError(
                "The Executor association has changed. Refresh before trying again.",
                code="executor_association_changed",
            )
        session.delete()
    # TODO: Reconcile associated unfinished work without claiming that remote processes stopped.
    return executor
