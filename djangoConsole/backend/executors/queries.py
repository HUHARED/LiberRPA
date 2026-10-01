# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.db.models.functions import Lower
from django.utils import timezone

from organizations.department_queries import get_department_tree, get_department_path
from organizations.models import Department, DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    resolve_organization_access,
    get_authorized_departments,
)

from .models import Executor, ExecutorSession
from .session_state import (
    get_executor_association_status,
    get_current_executor_sessions,
)

_INT_EXECUTORS_PER_PAGE = 50


@dataclass(frozen=True)
class ExecutorInfo:
    executor: Executor
    departmentPath: str
    canManage: bool
    session: ExecutorSession | None
    associationStatus: Literal["unassociated", "online", "offline"]


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
    currentTime: datetime


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
    executorIds: Iterable[uuid.UUID],
    currentTime: datetime,
) -> ExecutorReadContext:
    dictDepartmentById = get_department_tree(access.organization.id)
    setManagedDepartmentId = (
        set(
            get_authorized_departments(
                access, requiredRole=DepartmentRole.DEVELOPER
            ).values_list("id", flat=True)
        )
        if access.channel == AccessChannel.SESSION
        else set()
    )
    return ExecutorReadContext(
        departmentsById=dictDepartmentById,
        managedDepartmentIds=setManagedDepartmentId,
        sessionsByExecutorId=get_current_executor_sessions(
            access.organization.id, executorIds=executorIds, currentTime=currentTime
        ),
        currentTime=currentTime,
    )


def build_executor_info_list(
    executors: Sequence[Executor], context: ExecutorReadContext
) -> tuple[ExecutorInfo, ...]:
    """Build entries from one operation's loaded facts and shared observation time."""
    listExecutorInfo: list[ExecutorInfo] = []
    for executor in executors:
        department = context.departmentsById.get(executor.department_id)
        # A department deleted between these reads no longer has a current display entry.
        if department is None:
            continue
        session = context.sessionsByExecutorId.get(executor.id)
        listExecutorInfo.append(
            ExecutorInfo(
                executor=executor,
                departmentPath=get_department_path(department, context.departmentsById),
                canManage=executor.department_id in context.managedDepartmentIds,
                session=session,
                associationStatus=get_executor_association_status(
                    session, currentTime=context.currentTime
                ),
            )
        )
    return tuple(listExecutorInfo)


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
    currentTime = timezone.now()
    executorQuery = _get_executor_query(access)
    if departmentIds:
        executorQuery = executorQuery.filter(department_id__in=departmentIds)
    if name:
        executorQuery = executorQuery.filter(name__icontains=name)
    if dispatchStates:
        executorQuery = executorQuery.filter(dispatch_enabled__in=dispatchStates)
    if availableOnly:
        dictSessionByExecutorId = get_current_executor_sessions(
            access.organization.id,
            executorIds=executorQuery.values_list("id", flat=True),
            currentTime=currentTime,
        )
        executorQuery = executorQuery.exclude(pk__in=dictSessionByExecutorId)
    executorQuery = executorQuery.order_by(Lower("name"), "id")
    paginator = Paginator(executorQuery, _INT_EXECUTORS_PER_PAGE)
    executorPage = paginator.page(pageNumber)
    executors = list(executorPage.object_list)
    executorInfoEntries: tuple[ExecutorInfo, ...] = ()
    if executors:
        # NOTE: Selection already excluded every current association; do not read those sessions again.
        context = get_executor_read_context(
            access,
            executorIds=() if availableOnly else [executor.id for executor in executors],
            currentTime=currentTime,
        )
        executorInfoEntries = build_executor_info_list(executors, context)
    return ExecutorPageInfo(
        executors=executorInfoEntries,
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
    currentTime = timezone.now()
    executor = _get_executor_query(access).get(pk=executorId)
    context = get_executor_read_context(
        access, executorIds=(executor.id,), currentTime=currentTime
    )
    details = build_executor_info_list([executor], context)
    if not details:
        raise Executor.DoesNotExist
    return details[0]
