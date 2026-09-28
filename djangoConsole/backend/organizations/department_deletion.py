# FileName: department_deletion.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from typing import Literal

from django.db import transaction
from django.utils import timezone

from executors.models import Executor, ExecutorGroup
from assets.models import Asset
from data_queues.models import DataQueue
from shared_files.models import SharedFile, UploadSession
from operations.audit import record_audit

from .models import Department, DepartmentMembership
from .permissions import (
    AccessChannel,
    OrganizationAccessContext,
    resolve_organization_access,
    require_organization_admin,
)


@dataclass(frozen=True)
class DepartmentDeletionBlocker:
    code: Literal[
        "child_departments",
        "department_memberships",
        "executors",
        "executor_groups",
        "assets",
        "data_queues",
        "shared_files",
        "file_uploads",
    ]
    count: int


@dataclass(frozen=True)
class DepartmentDeletionInfo:
    departmentId: uuid.UUID
    departmentName: str
    blockers: tuple[DepartmentDeletionBlocker, ...]

    @property
    def canDelete(self) -> bool:
        return not self.blockers


class DepartmentDeletionBlockedError(Exception):
    def __init__(self, deletionInfo: DepartmentDeletionInfo) -> None:
        self.deletionInfo = deletionInfo
        super().__init__("The department has remaining dependencies.")


def get_department_deletion_info(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    departmentId: uuid.UUID,
) -> DepartmentDeletionInfo:
    """Describe current blockers without reserving the department or changing any rows."""
    _, department = _resolve_department_deletion_access(
        actorId, organizationId, channel, departmentId, forUpdate=False
    )
    return _build_department_deletion_info(department)


@transaction.atomic
def delete_department(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    departmentId: uuid.UUID,
) -> Department:
    """Delete an empty department while preserving its identity and historical links.

    Recheck current permission and dependencies inside the same organization lock used
    by department and membership writes. A previous preview grants no deletion rights.
    """
    access, department = _resolve_department_deletion_access(
        actorId, organizationId, channel, departmentId, forUpdate=True
    )
    deletionInfo = _build_department_deletion_info(department)
    if not deletionInfo.canDelete:
        raise DepartmentDeletionBlockedError(deletionInfo)

    department.deleted_at = timezone.now()
    department.save(update_fields=["deleted_at"])
    record_audit(
        "department.delete",
        actor=access.actor,
        organization=access.organization,
        target=department,
        channel=channel,
    )
    return department


def _resolve_department_deletion_access(
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    departmentId: uuid.UUID,
    *,
    forUpdate: bool,
) -> tuple[OrganizationAccessContext, Department]:
    access = resolve_organization_access(
        actorId=actorId,
        organizationId=organizationId,
        channel=channel,
        forUpdate=forUpdate,
    )
    require_organization_admin(access)
    department = Department.objects.get(
        pk=departmentId, organization=access.organization, deleted_at__isnull=True
    )
    return access, department


def _build_department_deletion_info(department: Department) -> DepartmentDeletionInfo:
    listBlocker: list[DepartmentDeletionBlocker] = []
    childCount = Department.objects.filter(
        parent=department, deleted_at__isnull=True
    ).count()
    if childCount:
        listBlocker.append(DepartmentDeletionBlocker("child_departments", childCount))

    # Explicit roles still block deletion when the account is inactive or an OrgAdmin.
    membershipCount = DepartmentMembership.objects.filter(department=department).count()
    if membershipCount:
        listBlocker.append(
            DepartmentDeletionBlocker("department_memberships", membershipCount)
        )

    executorCount = Executor.objects.filter(
        department=department, deleted_at__isnull=True
    ).count()
    if executorCount:
        listBlocker.append(DepartmentDeletionBlocker("executors", executorCount))

    groupCount = ExecutorGroup.objects.filter(
        department=department, deleted_at__isnull=True
    ).count()
    if groupCount:
        listBlocker.append(DepartmentDeletionBlocker("executor_groups", groupCount))

    assetCount = Asset.objects.filter(department=department).count()
    if assetCount:
        listBlocker.append(DepartmentDeletionBlocker("assets", assetCount))

    queueCount = DataQueue.objects.filter(department=department).count()
    if queueCount:
        listBlocker.append(DepartmentDeletionBlocker("data_queues", queueCount))

    fileCount = SharedFile.objects.filter(department=department).count()
    if fileCount:
        listBlocker.append(DepartmentDeletionBlocker("shared_files", fileCount))
    uploadCount = UploadSession.objects.filter(
        department_id=department.pk,
        state="receiving",
        expires_at__gt=timezone.now(),
    ).count()
    if uploadCount:
        listBlocker.append(DepartmentDeletionBlocker("file_uploads", uploadCount))

    # TODO: Include remaining business resources and unfinished Jobs when their models are implemented.
    # NOTE: Dependency writes must share the organization lock; retained history must not block deletion.
    return DepartmentDeletionInfo(
        departmentId=department.id,
        departmentName=department.name,
        blockers=tuple(listBlocker),
    )
