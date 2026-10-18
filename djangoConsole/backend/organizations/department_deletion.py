# FileName: department_deletion.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass

from django.utils import timezone

from executors.models import Executor, ExecutorGroup
from assets.models import Asset
from data_queues.models import DataQueue
from shared_files.contracts import UploadState
from shared_files.models import SharedFile, UploadSession
from packages.contracts import PackageUploadState
from packages.models import Package, PackageUpload
from schedules.models import Schedule
from runs.contracts import JobState
from runs.models import Job
from operations.audit import record_audit

from .contracts import DepartmentDeletionBlockerCode
from .models import Department, DepartmentMembership
from .permissions import (
    AccessChannel,
    OrganizationAccessContext,
    resolve_organization_access,
    require_organization_admin,
)


@dataclass(frozen=True)
class DepartmentDeletionBlocker:
    code: DepartmentDeletionBlockerCode
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


def _get_department_for_deletion(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> Department:
    require_organization_admin(access)
    return Department.objects.get(
        pk=departmentId, organization=access.organization, deleted_at__isnull=True
    )


def _build_department_deletion_info(department: Department) -> DepartmentDeletionInfo:
    listBlocker: list[DepartmentDeletionBlocker] = []
    intChildCount = Department.objects.filter(
        parent=department, deleted_at__isnull=True
    ).count()
    if intChildCount:
        listBlocker.append(
            DepartmentDeletionBlocker(
                DepartmentDeletionBlockerCode.CHILD_DEPARTMENTS, intChildCount
            )
        )

    # Explicit roles still block deletion when the account is inactive or an OrgAdmin.
    intMembershipCount = DepartmentMembership.objects.filter(
        department=department
    ).count()
    if intMembershipCount:
        listBlocker.append(
            DepartmentDeletionBlocker(
                DepartmentDeletionBlockerCode.DEPARTMENT_MEMBERSHIPS, intMembershipCount
            )
        )

    intExecutorCount = Executor.objects.filter(
        department=department, deleted_at__isnull=True
    ).count()
    if intExecutorCount:
        listBlocker.append(
            DepartmentDeletionBlocker(
                DepartmentDeletionBlockerCode.EXECUTORS, intExecutorCount
            )
        )

    intGroupCount = ExecutorGroup.objects.filter(
        department=department, deleted_at__isnull=True
    ).count()
    if intGroupCount:
        listBlocker.append(
            DepartmentDeletionBlocker(
                DepartmentDeletionBlockerCode.EXECUTOR_GROUPS, intGroupCount
            )
        )

    intAssetCount = Asset.objects.filter(department=department).count()
    if intAssetCount:
        listBlocker.append(
            DepartmentDeletionBlocker(DepartmentDeletionBlockerCode.ASSETS, intAssetCount)
        )

    intQueueCount = DataQueue.objects.filter(department=department).count()
    if intQueueCount:
        listBlocker.append(
            DepartmentDeletionBlocker(
                DepartmentDeletionBlockerCode.DATA_QUEUES, intQueueCount
            )
        )

    intFileCount = SharedFile.objects.filter(department=department).count()
    if intFileCount:
        listBlocker.append(
            DepartmentDeletionBlocker(
                DepartmentDeletionBlockerCode.SHARED_FILES, intFileCount
            )
        )
    intUploadCount = UploadSession.objects.filter(
        department_id=department.pk,
        state=UploadState.RECEIVING,
        expires_at__gt=timezone.now(),
    ).count()
    if intUploadCount:
        listBlocker.append(
            DepartmentDeletionBlocker(
                DepartmentDeletionBlockerCode.FILE_UPLOADS, intUploadCount
            )
        )

    for blocker in (
        DepartmentDeletionBlocker(
            DepartmentDeletionBlockerCode.PACKAGES,
            Package.objects.filter(department=department).count(),
        ),
        DepartmentDeletionBlocker(
            DepartmentDeletionBlockerCode.PACKAGE_UPLOADS,
            PackageUpload.objects.filter(
                department_id=department.pk,
                state=PackageUploadState.RECEIVING,
                expires_at__gt=timezone.now(),
            ).count(),
        ),
        DepartmentDeletionBlocker(
            DepartmentDeletionBlockerCode.SCHEDULES,
            Schedule.objects.filter(
                department=department, deleted_at__isnull=True
            ).count(),
        ),
        DepartmentDeletionBlocker(
            DepartmentDeletionBlockerCode.ACTIVE_JOBS,
            Job.objects
            .filter(department=department)
            .exclude(state=JobState.FINISHED)
            .count(),
        ),
    ):
        if blocker.count:
            listBlocker.append(blocker)
    # NOTE: Dependency writes must share the organization lock; retained history must not block deletion.
    return DepartmentDeletionInfo(
        departmentId=department.id,
        departmentName=department.name,
        blockers=tuple(listBlocker),
    )


def get_department_deletion_info(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    departmentId: uuid.UUID,
) -> DepartmentDeletionInfo:
    """Describe current blockers without reserving the department or changing any rows."""
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    department = _get_department_for_deletion(access, departmentId)
    return _build_department_deletion_info(department)


def delete_department(
    *,
    access: OrganizationAccessContext,
    departmentId: uuid.UUID,
) -> Department:
    """Delete an empty department while preserving its identity and historical links.

    The caller supplies rechecked access and owns the transaction through response construction.
    Recheck current permission and dependencies under the organization lock; a previous preview grants no deletion rights.
    """
    department = _get_department_for_deletion(access, departmentId)
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
        channel=access.channel,
    )
    return department
