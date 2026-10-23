# FileName: member_queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Sequence
from typing import cast

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.db.models.functions import Lower

from accounts.contracts import UserResponse
from accounts.models import User
from console_project.constants import INT_LIST_PAGE_SIZE
from console_project.contracts import PaginationResponse

from .department_queries import get_department_path
from .contracts import (
    DepartmentRole,
    MemberDepartmentResponse,
    MemberDepartmentRoleResponse,
    MemberResponse,
    MemberListResponse,
    MemberDetailsResponse,
)
from .models import Membership, Department, DepartmentMembership
from .permissions import OrganizationAccessContext, require_organization_admin


def _get_member_query(access: OrganizationAccessContext) -> QuerySet[Membership]:
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


def _get_member_response_list(
    memberships: Sequence[Membership], organizationId: uuid.UUID
) -> list[MemberResponse]:
    if not memberships:
        return []
    dictDepartmentById = (
        Department.objects
        .filter(organization_id=organizationId, deleted_at__isnull=True)
        .only("id", "name", "parent")
        .in_bulk()
    )
    dictRoleByMemberId: dict[uuid.UUID, list[MemberDepartmentRoleResponse]] = {
        membership.user_id: [] for membership in memberships
    }
    for memberId, departmentId, strRole in DepartmentMembership.objects.filter(
        membership_id__in=dictRoleByMemberId,
        department_id__in=dictDepartmentById,
    ).values_list("membership_id", "department_id", "role"):
        department = dictDepartmentById[departmentId]
        dictRoleByMemberId[memberId].append(
            MemberDepartmentRoleResponse(
                department=MemberDepartmentResponse(
                    id=department.id,
                    name=department.name,
                    path=get_department_path(department, dictDepartmentById),
                ),
                role=DepartmentRole(strRole),
            )
        )

    listMember: list[MemberResponse] = []
    for membership in memberships:
        user = cast(User, membership.user)
        listMember.append(
            MemberResponse(
                user=UserResponse(id=user.id, email=user.email, username=user.username),
                is_org_admin=membership.is_org_admin,
                department_roles=sorted(
                    dictRoleByMemberId[user.id],
                    key=lambda role: (
                        role.department.path.casefold(),
                        role.department.id,
                    ),
                ),
                notes=membership.notes,
                joined_at=membership.joined_at,
            )
        )
    return listMember


def get_member_list(
    *,
    access: OrganizationAccessContext,
    pageNumber: int = 1,
) -> MemberListResponse:
    """Read one ordered page of current members and their explicit department roles."""
    membershipQuery = _get_member_query(access).order_by(
        Lower("user__username"), "user__email", "user_id"
    )
    paginator = Paginator(membershipQuery, INT_LIST_PAGE_SIZE)
    memberPage = paginator.page(pageNumber)
    return MemberListResponse(
        members=_get_member_response_list(
            list(memberPage.object_list), access.organization.pk
        ),
        pagination=PaginationResponse(
            page=memberPage.number,
            page_size=INT_LIST_PAGE_SIZE,
            total_count=paginator.count,
            total_pages=paginator.num_pages,
        ),
    )


def get_member_details(
    *,
    access: OrganizationAccessContext,
    userId: uuid.UUID,
) -> MemberDetailsResponse:
    """Read one current organization member without exposing account credentials."""
    membership = _get_member_query(access).get(user_id=userId)
    return MemberDetailsResponse(
        member=_get_member_response_list([membership], access.organization.pk)[0]
    )
