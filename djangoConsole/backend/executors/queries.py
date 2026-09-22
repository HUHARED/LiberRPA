# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.db.models.functions import Lower

from organizations.department_queries import get_department_path
from organizations.models import Department, DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
    resolve_organization_access,
)

from .models import Executor

_INT_EXECUTORS_PER_PAGE = 50


@dataclass(frozen=True)
class ExecutorInfo:
    executor: Executor
    departmentPath: str
    canManage: bool


@dataclass(frozen=True)
class ExecutorPageInfo:
    executors: tuple[ExecutorInfo, ...]
    page: int
    pageSize: int
    totalCount: int
    totalPages: int


def _get_executor_query(access: OrganizationAccessContext) -> QuerySet[Executor]:
    return Executor.objects.filter(
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
        deleted_at__isnull=True,
    ).select_related("department")


def _get_executor_info_list(
    executors: Sequence[Executor], access: OrganizationAccessContext
) -> tuple[ExecutorInfo, ...]:
    if not executors:
        return ()
    dictDepartmentById = (
        Department.objects
        .filter(organization=access.organization, deleted_at__isnull=True)
        .only("id", "name", "parent")
        .in_bulk()
    )
    setManagedDepartmentId = (
        set(
            get_authorized_departments(
                access, requiredRole=DepartmentRole.DEVELOPER
            ).values_list("id", flat=True)
        )
        if access.channel == AccessChannel.SESSION
        else set()
    )
    return tuple(
        ExecutorInfo(
            executor=executor,
            departmentPath=get_department_path(
                dictDepartmentById[executor.department_id], dictDepartmentById
            ),
            canManage=executor.department_id in setManagedDepartmentId,
        )
        for executor in executors
        # A department deleted between these reads no longer has a current display entry.
        if executor.department_id in dictDepartmentById
    )


def get_executor_list(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    pageNumber: int = 1,
    departmentIds: tuple[uuid.UUID, ...] = (),
    name: str = "",
    dispatchStates: tuple[bool, ...] = (),
) -> ExecutorPageInfo:
    """Filter within current visible departments; request filters never expand that scope."""
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    executorQuery = _get_executor_query(access)
    if departmentIds:
        executorQuery = executorQuery.filter(department_id__in=departmentIds)
    if name:
        executorQuery = executorQuery.filter(name__icontains=name)
    if dispatchStates:
        executorQuery = executorQuery.filter(dispatch_enabled__in=dispatchStates)
    executorQuery = executorQuery.order_by(Lower("name"), "id")
    paginator = Paginator(executorQuery, _INT_EXECUTORS_PER_PAGE)
    executorPage = paginator.page(pageNumber)
    return ExecutorPageInfo(
        executors=_get_executor_info_list(list(executorPage.object_list), access),
        page=executorPage.number,
        pageSize=_INT_EXECUTORS_PER_PAGE,
        totalCount=paginator.count,
        totalPages=paginator.num_pages,
    )


def get_executor_details(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    executorId: uuid.UUID,
) -> ExecutorInfo:
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    executor = _get_executor_query(access).get(pk=executorId)
    details = _get_executor_info_list([executor], access)
    if not details:
        raise Executor.DoesNotExist
    return details[0]
