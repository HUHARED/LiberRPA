# FileName: member_queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.db.models.functions import Lower

from accounts.models import User

from .department_queries import get_department_path
from .models import Department, DepartmentMembership, DepartmentRole, Membership
from .permissions import (
    AccessChannel,
    require_organization_admin,
    resolve_organization_access,
)

_INT_MEMBERS_PER_PAGE = 50


@dataclass(frozen=True)
class MemberDepartmentRoleInfo:
    departmentId: uuid.UUID
    departmentName: str
    departmentPath: str
    role: DepartmentRole


@dataclass(frozen=True)
class MemberInfo:
    userId: uuid.UUID
    email: str
    username: str
    isOrgAdmin: bool
    departmentRoles: tuple[MemberDepartmentRoleInfo, ...]
    notes: str
    joinedAt: datetime


@dataclass(frozen=True)
class MemberPageInfo:
    members: tuple[MemberInfo, ...]
    page: int
    pageSize: int
    totalCount: int
    totalPages: int


def _get_member_query(
    actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> QuerySet[Membership]:
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    require_organization_admin(access)
    return (
        Membership.objects
        .filter(organization=access.organization)
        .select_related("user")
        .only(
            "user__id",
            "user__email",
            "user__username",
            "organization_id",
            "is_org_admin",
            "notes",
            "joined_at",
        )
    )


def _get_member_info_list(
    memberships: Sequence[Membership], organizationId: uuid.UUID
) -> tuple[MemberInfo, ...]:
    if not memberships:
        return ()
    dictDepartmentById = (
        Department.objects
        .filter(organization_id=organizationId, deleted_at__isnull=True)
        .only("id", "name", "parent")
        .in_bulk()
    )
    dictRoleByMemberId: dict[uuid.UUID, list[MemberDepartmentRoleInfo]] = {
        membership.user_id: [] for membership in memberships
    }
    for memberId, departmentId, role in DepartmentMembership.objects.filter(
        membership_id__in=dictRoleByMemberId,
        department_id__in=dictDepartmentById,
    ).values_list("membership_id", "department_id", "role"):
        department = dictDepartmentById[departmentId]
        dictRoleByMemberId[memberId].append(
            MemberDepartmentRoleInfo(
                departmentId=department.id,
                departmentName=department.name,
                departmentPath=get_department_path(department, dictDepartmentById),
                role=DepartmentRole(role),
            )
        )

    listMemberInfo: list[MemberInfo] = []
    for membership in memberships:
        user = cast(User, membership.user)
        listMemberInfo.append(
            MemberInfo(
                userId=user.id,
                email=user.email,
                username=user.username,
                isOrgAdmin=membership.is_org_admin,
                departmentRoles=tuple(
                    sorted(
                        dictRoleByMemberId[user.id],
                        key=lambda roleInfo: (
                            roleInfo.departmentPath.casefold(),
                            roleInfo.departmentId,
                        ),
                    )
                ),
                notes=membership.notes,
                joinedAt=membership.joined_at,
            )
        )
    return tuple(listMemberInfo)


def get_member_list(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    pageNumber: int = 1,
) -> MemberPageInfo:
    """Read one ordered page of current members and their explicit department roles."""
    membershipQuery = _get_member_query(actorId, organizationId, channel).order_by(
        Lower("user__username"), "user__email", "user_id"
    )
    paginator = Paginator(membershipQuery, _INT_MEMBERS_PER_PAGE)
    memberPage = paginator.page(pageNumber)
    return MemberPageInfo(
        members=_get_member_info_list(list(memberPage.object_list), organizationId),
        page=memberPage.number,
        pageSize=_INT_MEMBERS_PER_PAGE,
        totalCount=paginator.count,
        totalPages=paginator.num_pages,
    )


def get_member_details(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
) -> MemberInfo:
    """Read one current organization member without exposing account credentials."""
    membership = _get_member_query(actorId, organizationId, channel).get(user_id=userId)
    return _get_member_info_list([membership], organizationId)[0]
