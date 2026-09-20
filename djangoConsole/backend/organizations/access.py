# FileName: access.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from .models import Department, DepartmentRole, Organization
from .permissions import (
    AccessChannel,
    OrganizationAccess,
    get_authorized_departments,
    get_current_membership,
    is_organization_business_available,
)


@dataclass(frozen=True)
class OrganizationInfo:
    id: uuid.UUID
    name: str
    suspended_at: datetime | None
    deletion_requested_at: datetime | None
    deletion_due_at: datetime | None
    deletion_started_at: datetime | None


@dataclass(frozen=True)
class DepartmentAccessInfo:
    id: uuid.UUID
    name: str
    path: str
    # OrgAdmin access is organization-wide, so its department role is None.
    role: DepartmentRole | None


@dataclass(frozen=True)
class AccountAccessInfo:
    """Display data for this request; subsequent operations resolve their current permissions."""

    organization: OrganizationInfo
    is_org_admin: bool
    business_available: bool
    departments: tuple[DepartmentAccessInfo, ...]


def _get_department_path(
    department: Department, departmentsById: dict[uuid.UUID, Department]
) -> str:
    names = [department.name]
    parentId = department.parent_id
    # Department write services already enforce a valid tree within one organization.
    while parentId is not None:
        parent = departmentsById[parentId]
        names.append(parent.name)
        parentId = parent.parent_id
    return "/".join(reversed(names))


def _get_department_access(
    access: OrganizationAccess,
) -> tuple[DepartmentAccessInfo, ...]:
    departments = get_authorized_departments(access, requiredRole=DepartmentRole.OPERATOR)
    rolesByDepartment: dict[uuid.UUID, DepartmentRole | None]
    if access.is_org_admin:
        rolesByDepartment = dict.fromkeys(departments.values_list("id", flat=True))
    else:
        # Reuse the membership join already scoped by get_authorized_departments().
        rolesByDepartment = {
            departmentId: DepartmentRole(role)
            for departmentId, role in departments.values_list("id", "memberships__role")
        }
    if not rolesByDepartment:
        return ()

    # Load only path components; ancestor names do not grant access to ancestor departments.
    departmentsById = {
        department.pk: department
        for department in Department.objects.filter(
            organization=access.organization, deleted_at__isnull=True
        ).only("id", "name", "parent")
    }
    result = [
        DepartmentAccessInfo(
            id=department.pk,
            name=department.name,
            path=_get_department_path(department, departmentsById),
            role=rolesByDepartment[department.pk],
        )
        for department in departmentsById.values()
        if department.pk in rolesByDepartment
    ]
    return tuple(
        sorted(result, key=lambda department: (department.path.casefold(), department.id))
    )


def get_account_access_info(*, actorId: uuid.UUID) -> AccountAccessInfo:
    """Describe the authenticated account's organization and currently available departments.

    Frozen organizations expose identity and service state for their restricted status page.
    No organization or department permissions are stored in the login session.
    """
    membership = get_current_membership(actorId=actorId)
    organization = cast(Organization, membership.organization)
    businessAvailable = is_organization_business_available(organization)
    departmentAccess: tuple[DepartmentAccessInfo, ...] = ()
    if businessAvailable:
        access = OrganizationAccess(
            actor_id=membership.user_id,
            organization=organization,
            is_org_admin=membership.is_org_admin,
            channel=AccessChannel.SESSION,
        )
        departmentAccess = _get_department_access(access)

    return AccountAccessInfo(
        organization=OrganizationInfo(
            id=organization.pk,
            name=organization.name,
            suspended_at=organization.suspended_at,
            deletion_requested_at=organization.deletion_requested_at,
            deletion_due_at=organization.deletion_due_at,
            deletion_started_at=organization.deletion_started_at,
        ),
        is_org_admin=membership.is_org_admin,
        business_available=businessAvailable,
        departments=departmentAccess,
    )
