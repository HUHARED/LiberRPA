# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime
from typing import cast

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError
from console_project.config import LimitsConfig
from organizations.models import DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
    resolve_organization_access,
)

from .models import Executor


@sensitive_variables()
def _lock_executor_access(
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> OrganizationAccessContext:
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to manage executors.")
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel, forUpdate=True
    )
    # Resolve again after the organization/account locks; a waiting write cannot reuse a revoked session.
    actor = User.objects.get(pk=actorId)
    if (
        sessionExpiresAt <= timezone.now()
        or not sessionAuthHash
        or not constant_time_compare(sessionAuthHash, actor.get_session_auth_hash())
    ):
        raise SessionInvalidatedError("The current session is no longer valid.")
    return access


def _require_executor_management(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> None:
    if not get_authorized_departments(
        access, requiredRole=DepartmentRole.DEVELOPER
    ).filter(pk=departmentId).exists():
        raise PermissionDenied("Developer access is required to manage executors.")


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
    _require_executor_management(access, executor.department_id)
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
    access = _lock_executor_access(
        actorId, organizationId, channel, sessionAuthHash, sessionExpiresAt
    )
    department = get_authorized_departments(
        access, requiredRole=DepartmentRole.OPERATOR
    ).get(pk=departmentId)
    _require_executor_management(access, department.id)
    executor = Executor(department=department, name=name.strip(), notes=notes)
    executor.full_clean()
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    # Paused and unassociated records consume capacity; deleted identities do not.
    if Executor.objects.filter(
        department__organization=access.organization, deleted_at__isnull=True
    ).count() >= limits.maxExecutorsPerOrganization:
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
    access = _lock_executor_access(
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
    access = _lock_executor_access(
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
    access = _lock_executor_access(
        actorId, organizationId, channel, sessionAuthHash, sessionExpiresAt
    )
    executor = _get_executor_for_management(access, executorId)
    # TODO: Check Schedule/group/current-work references and revoke associations when those models are added.
    # Reference creation must share this organization lock; retained history must not block deletion.
    executor.deleted_at = timezone.now()
    executor.save(update_fields=["deleted_at"])
    return executor
