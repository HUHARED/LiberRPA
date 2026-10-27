# FileName: group_queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections import Counter

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.db.models.functions import Lower
from django.utils import timezone

from console_project.constants import INT_LIST_PAGE_SIZE
from organizations.department_queries import get_department_path
from organizations.contracts import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)
from schedules.models import Schedule

from .contracts import (
    ExecutorAssociationStatus,
    ExecutorDepartmentResponse,
    ExecutorScheduleReferenceResponse,
    ExecutorGroupListEntryResponse,
    ExecutorGroupListResponse,
    ExecutorGroupDetailsEntryResponse,
    ExecutorGroupDetailsResponse,
)
from .models import Executor, ExecutorGroup, ExecutorGroupMember
from .queries import (
    build_executor_list_entry,
    get_executor_read_context,
    build_executor_info_list,
)
from .session_state import get_executor_association_status


def _get_group_query(access: OrganizationAccessContext) -> QuerySet[ExecutorGroup]:
    return ExecutorGroup.objects.filter(
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
    ).select_related("department")


def get_executor_group_list(
    *,
    access: OrganizationAccessContext,
    pageNumber: int = 1,
    departmentIds: tuple[uuid.UUID, ...] = (),
    name: str = "",
) -> ExecutorGroupListResponse:
    groupQuery = _get_group_query(access)
    if departmentIds:
        groupQuery = groupQuery.filter(department_id__in=departmentIds)
    if name:
        groupQuery = groupQuery.filter(name__icontains=name)
    paginator = Paginator(groupQuery.order_by(Lower("name"), "id"), INT_LIST_PAGE_SIZE)
    groupPage = paginator.page(pageNumber)
    groups = list(groupPage.object_list)
    groupEntries: list[ExecutorGroupListEntryResponse] = []
    if groups:
        currentTime = timezone.now()
        memberships = list(
            ExecutorGroupMember.objects.filter(
                group_id__in=[group.id for group in groups],
                executor__deleted_at__isnull=True,
            ).values_list("group_id", "executor_id")
        )
        context = get_executor_read_context(
            access,
            executorIds={executorId for _, executorId in memberships},
            currentTime=currentTime,
        )
        onlineExecutorIds = {
            executorId
            for executorId, session in context.sessionsByExecutorId.items()
            if get_executor_association_status(session, currentTime=currentTime)
            == ExecutorAssociationStatus.ONLINE
        }
        memberCounts: Counter[uuid.UUID] = Counter()
        onlineCounts: Counter[uuid.UUID] = Counter()
        for groupId, executorId in memberships:
            memberCounts[groupId] += 1
            if executorId in onlineExecutorIds:
                onlineCounts[groupId] += 1
        groupEntries = [
            ExecutorGroupListEntryResponse(
                id=group.id,
                name=group.name,
                department_id=group.department_id,
                notes=group.notes,
                created_at=group.created_at,
                department=ExecutorDepartmentResponse(
                    id=group.department_id,
                    name=group.department.name,
                    path=get_department_path(
                        context.departmentsById[group.department_id],
                        context.departmentsById,
                    ),
                ),
                can_manage=group.department_id in context.managedDepartmentIds,
                member_count=memberCounts[group.id],
                online_count=onlineCounts[group.id],
                is_empty=memberCounts[group.id] == 0,
            )
            for group in groups
            if group.department_id in context.departmentsById
        ]
    return ExecutorGroupListResponse(
        executor_groups=groupEntries,
        page=groupPage.number,
        page_size=INT_LIST_PAGE_SIZE,
        total_count=paginator.count,
        total_pages=paginator.num_pages,
    )


def get_executor_group_details(
    *,
    access: OrganizationAccessContext,
    groupId: uuid.UUID,
) -> ExecutorGroupDetailsResponse:
    currentTime = timezone.now()
    group = _get_group_query(access).get(pk=groupId)
    members = list(
        Executor.objects
        .filter(
            group_memberships__group=group,
            department_id=group.department_id,
            deleted_at__isnull=True,
        )
        .select_related("department")
        .order_by(Lower("name"), "id")
    )
    context = get_executor_read_context(
        access,
        executorIds=[executor.id for executor in members],
        currentTime=currentTime,
    )
    if group.department_id not in context.departmentsById:
        raise ExecutorGroup.DoesNotExist
    memberInfoEntries = build_executor_info_list(members, context)
    # NOTE: Count the same statuses returned for members; serialization must not observe a later time.
    return ExecutorGroupDetailsResponse(
        executor_group=ExecutorGroupDetailsEntryResponse(
            id=group.id,
            name=group.name,
            department_id=group.department_id,
            notes=group.notes,
            created_at=group.created_at,
            department=ExecutorDepartmentResponse(
                id=group.department_id,
                name=group.department.name,
                path=get_department_path(
                    context.departmentsById[group.department_id], context.departmentsById
                ),
            ),
            can_manage=group.department_id in context.managedDepartmentIds,
            member_count=len(memberInfoEntries),
            online_count=sum(
                member.associationStatus == ExecutorAssociationStatus.ONLINE
                for member in memberInfoEntries
            ),
            is_empty=not memberInfoEntries,
            members=[build_executor_list_entry(member) for member in memberInfoEntries],
            referencing_schedules=[
                ExecutorScheduleReferenceResponse(
                    id=schedule.id, name=schedule.name, enabled=schedule.enabled
                )
                for schedule in (
                    Schedule.objects
                    .filter(group_id=groupId)
                    .only("id", "name", "enabled")
                    .order_by("name", "id")
                )
            ],
        )
    )


def get_executor_group_references(executor: Executor) -> tuple[ExecutorGroup, ...]:
    """List current references after the caller has authorized this Executor's department."""
    return tuple(
        ExecutorGroup.objects.filter(
            memberships__executor=executor,
            department_id=executor.department_id,
        ).order_by(Lower("name"), "id")
    )
