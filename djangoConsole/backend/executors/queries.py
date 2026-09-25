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
from django.utils import timezone

from organizations.department_queries import get_department_path
from organizations.models import Department, DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
    resolve_organization_access,
)

from .models import Executor, ExecutorSession
from .session_state import get_current_executor_sessions

_INT_EXECUTORS_PER_PAGE = 50


@dataclass(frozen=True)
class ExecutorInfo:
    executor: Executor
    departmentPath: str
    canManage: bool
    session: ExecutorSession | None


@dataclass(frozen=True)
class ExecutorPageInfo:
    executors: tuple[ExecutorInfo, ...]
    page: int
    pageSize: int
    totalCount: int
    totalPages: int


@dataclass(frozen=True)
class ExecutorReadContext:
    """Department and session facts loaded once for the current read operation."""

    departmentsById: dict[uuid.UUID, Department]
    managedDepartmentIds: set[uuid.UUID]
    sessionsByExecutorId: dict[uuid.UUID, ExecutorSession]


def _get_executor_query(access: OrganizationAccessContext) -> QuerySet[Executor]:
    return Executor.objects.filter(
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
        deleted_at__isnull=True,
    ).select_related("department")


def get_executor_read_context(
    access: OrganizationAccessContext,
    *,
    sessionsByExecutorId: dict[uuid.UUID, ExecutorSession] | None = None,
) -> ExecutorReadContext:
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
    if sessionsByExecutorId is None:
        sessionsByExecutorId = get_current_executor_sessions(
            access.organization.id, currentTime=timezone.now()
        )
    return ExecutorReadContext(
        departmentsById=dictDepartmentById,
        managedDepartmentIds=setManagedDepartmentId,
        sessionsByExecutorId=sessionsByExecutorId,
    )


def build_executor_info_list(
    executors: Sequence[Executor], context: ExecutorReadContext
) -> tuple[ExecutorInfo, ...]:
    """Build display entries from authorized records and already loaded read facts."""
    return tuple(
        ExecutorInfo(
            executor=executor,
            departmentPath=get_department_path(
                context.departmentsById[executor.department_id], context.departmentsById
            ),
            canManage=executor.department_id in context.managedDepartmentIds,
            session=context.sessionsByExecutorId.get(executor.id),
        )
        for executor in executors
        # A department deleted between these reads no longer has a current display entry.
        if executor.department_id in context.departmentsById
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
    availableOnly: bool = False,
) -> ExecutorPageInfo:
    """Filter within current visible departments; request filters never expand that scope."""
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    executorQuery = _get_executor_query(access)
    dictSessionByExecutorId = None
    if availableOnly:
        dictSessionByExecutorId = get_current_executor_sessions(
            access.organization.id, currentTime=timezone.now()
        )
        executorQuery = executorQuery.exclude(pk__in=dictSessionByExecutorId)
    if departmentIds:
        executorQuery = executorQuery.filter(department_id__in=departmentIds)
    if name:
        executorQuery = executorQuery.filter(name__icontains=name)
    if dispatchStates:
        executorQuery = executorQuery.filter(dispatch_enabled__in=dispatchStates)
    executorQuery = executorQuery.order_by(Lower("name"), "id")
    paginator = Paginator(executorQuery, _INT_EXECUTORS_PER_PAGE)
    executorPage = paginator.page(pageNumber)
    executors = list(executorPage.object_list)
    executorInfo: tuple[ExecutorInfo, ...] = ()
    if executors:
        context = get_executor_read_context(
            access, sessionsByExecutorId=dictSessionByExecutorId
        )
        executorInfo = build_executor_info_list(executors, context)
    return ExecutorPageInfo(
        executors=executorInfo,
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
    details = build_executor_info_list([executor], get_executor_read_context(access))
    if not details:
        raise Executor.DoesNotExist
    return details[0]
