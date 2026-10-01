# FileName: group_services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
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
from .models import Executor, ExecutorGroup, ExecutorGroupMember

# NOTE: Call these writes with freshly locked Session access inside the caller's transaction.


@dataclass(frozen=True)
class ExecutorGroupWriteResult:
    group: ExecutorGroup
    executorIds: tuple[uuid.UUID, ...]


def _get_group_for_management(
    access: OrganizationAccessContext, groupId: uuid.UUID
) -> ExecutorGroup:
    group = ExecutorGroup.objects.get(
        pk=groupId,
        deleted_at__isnull=True,
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
    )
    require_executor_management(access, group.department_id)
    return group


def _validate_group_members(
    group: ExecutorGroup, executorIds: tuple[uuid.UUID, ...]
) -> None:
    if len(set(executorIds)) != len(executorIds):
        raise ValidationError({"executor_ids": "Select each Executor only once."})
    intMemberCount = Executor.objects.filter(
        pk__in=executorIds, department_id=group.department_id, deleted_at__isnull=True
    ).count()
    if intMemberCount != len(executorIds):
        # Do not disclose whether an unavailable ID exists in another department or organization.
        raise ValidationError({
            "executor_ids": "Select current Executors from the group's department."
        })
    # Association, account access, online state, and dispatch are runtime facts, not membership requirements.


def _save_group_members(group: ExecutorGroup, executorIds: tuple[uuid.UUID, ...]) -> None:
    memberships = ExecutorGroupMember.objects.filter(group=group)
    currentIds = set(memberships.values_list("executor_id", flat=True))
    memberships.exclude(executor_id__in=executorIds).delete()
    ExecutorGroupMember.objects.bulk_create([
        ExecutorGroupMember(group=group, executor_id=executorId)
        for executorId in executorIds
        if executorId not in currentIds
    ])
    # TODO: Recheck unpermitted group assignments when Jobs exist; never rewrite permitted or actual Runs.
    # An empty group does not change any referencing Schedule's Enabled flag or emit a notification.


@sensitive_variables()
def create_executor_group(
    access: OrganizationAccessContext,
    *,
    departmentId: uuid.UUID,
    name: str,
    notes: str,
    executorIds: tuple[uuid.UUID, ...],
) -> ExecutorGroupWriteResult:
    department = get_authorized_departments(
        access, requiredRole=DepartmentRole.OPERATOR
    ).get(pk=departmentId)
    require_executor_management(access, department.id)
    group = ExecutorGroup(department=department, name=name.strip(), notes=notes)
    group.full_clean()
    _validate_group_members(group, executorIds)
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if (
        ExecutorGroup.objects.filter(
            department__organization=access.organization, deleted_at__isnull=True
        ).count()
        >= limits.maxExecutorGroupsPerOrganization
    ):
        raise ValidationError(
            "This organization has reached its limit of %(limit)s Executor groups.",
            code="executor_group_count_limit",
            params={"limit": limits.maxExecutorGroupsPerOrganization},
        )
    group.save(force_insert=True)
    _save_group_members(group, executorIds)
    record_audit(
        "executor_group.create",
        actor=access.actor,
        organization=access.organization,
        target=group,
        channel=access.channel,
        before={},
    )
    return ExecutorGroupWriteResult(group, executorIds)


@sensitive_variables()
def update_executor_group(
    access: OrganizationAccessContext,
    *,
    groupId: uuid.UUID,
    name: str,
    notes: str,
    executorIds: tuple[uuid.UUID, ...],
) -> ExecutorGroupWriteResult:
    """Save the complete form and membership set together, including an explicitly empty set."""
    group = _get_group_for_management(access, groupId)
    dictAuditBefore = get_audit_snapshot(group)
    group.name = name.strip()
    group.notes = notes
    group.full_clean()
    _validate_group_members(group, executorIds)
    group.save(update_fields=["name", "notes"])
    _save_group_members(group, executorIds)
    record_audit(
        "executor_group.update",
        actor=access.actor,
        organization=access.organization,
        target=group,
        channel=access.channel,
        before=dictAuditBefore,
    )
    return ExecutorGroupWriteResult(group, executorIds)


@sensitive_variables()
def delete_executor_group(
    access: OrganizationAccessContext,
    *,
    groupId: uuid.UUID,
) -> ExecutorGroup:
    """Remove memberships and retain the group identity without changing any Executor."""
    group = _get_group_for_management(access, groupId)
    # TODO: Block undeleted Schedule and unfinished group Job references when those models exist.
    # Reference creation must use the same organization lock; completed history must not block deletion.
    ExecutorGroupMember.objects.filter(group=group).delete()
    group.deleted_at = timezone.now()
    group.save(update_fields=["deleted_at"])
    record_audit(
        "executor_group.delete",
        actor=access.actor,
        organization=access.organization,
        target=group,
        channel=access.channel,
    )
    return group
