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
    OrganizationAccessContext,
    get_authorized_departments,
    get_current_membership,
    is_organization_business_available,
)


@dataclass(frozen=True)
class OrganizationInfo:
    id: uuid.UUID
    name: str
    suspendedAt: datetime | None
    deletionRequestedAt: datetime | None
    deletionDueAt: datetime | None
    deletionStartedAt: datetime | None


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
    isOrgAdmin: bool
    businessAvailable: bool
    departments: tuple[DepartmentAccessInfo, ...]


def _get_department_path(
    department: Department, departmentsById: dict[uuid.UUID, Department]
) -> str:
    listDepartmentName = [department.name]
    parentId = department.parent_id
    # Department write services already enforce a valid tree within one organization.
    while parentId is not None:
        parentDepartment = departmentsById[parentId]
        listDepartmentName.append(parentDepartment.name)
        parentId = parentDepartment.parent_id
    return "/".join(reversed(listDepartmentName))


def _get_department_access_info(
    access: OrganizationAccessContext,
) -> tuple[DepartmentAccessInfo, ...]:
    departmentQuery = get_authorized_departments(
        access, requiredRole=DepartmentRole.OPERATOR
    )
    dictRoleByDepartmentId: dict[uuid.UUID, DepartmentRole | None]
    if access.isOrgAdmin:
        dictRoleByDepartmentId = dict.fromkeys(
            departmentQuery.values_list("id", flat=True)
        )
    else:
        # Reuse the membership join already scoped by get_authorized_departments().
        dictRoleByDepartmentId = {
            departmentId: DepartmentRole(role)
            for departmentId, role in departmentQuery.values_list(
                "id", "memberships__role"
            )
        }
    if not dictRoleByDepartmentId:
        return ()

    # Load only path components; ancestor names do not grant access to ancestor departments.
    dictDepartmentById = {
        department.pk: department
        for department in Department.objects.filter(
            organization=access.organization, deleted_at__isnull=True
        ).only("id", "name", "parent")
    }
    listDepartmentAccessInfo = [
        DepartmentAccessInfo(
            id=department.pk,
            name=department.name,
            path=_get_department_path(department, dictDepartmentById),
            role=dictRoleByDepartmentId[department.pk],
        )
        for department in dictDepartmentById.values()
        if department.pk in dictRoleByDepartmentId
    ]
    return tuple(
        sorted(
            listDepartmentAccessInfo,
            key=lambda departmentAccessInfo: (
                departmentAccessInfo.path.casefold(),
                departmentAccessInfo.id,
            ),
        )
    )


def get_account_access_info(*, actorId: uuid.UUID) -> AccountAccessInfo:
    """Describe the authenticated account's organization and currently available departments.

    Frozen organizations expose identity and service state for their restricted status page.
    No organization or department permissions are stored in the login session.
    """
    membership = get_current_membership(actorId=actorId)
    organization = cast(Organization, membership.organization)
    businessAvailable = is_organization_business_available(organization)
    departmentAccessEntries: tuple[DepartmentAccessInfo, ...] = ()
    if businessAvailable:
        access = OrganizationAccessContext(
            actorId=membership.user_id,
            organization=organization,
            isOrgAdmin=membership.is_org_admin,
            channel=AccessChannel.SESSION,
        )
        departmentAccessEntries = _get_department_access_info(access)

    return AccountAccessInfo(
        organization=OrganizationInfo(
            id=organization.pk,
            name=organization.name,
            suspendedAt=organization.suspended_at,
            deletionRequestedAt=organization.deletion_requested_at,
            deletionDueAt=organization.deletion_due_at,
            deletionStartedAt=organization.deletion_started_at,
        ),
        isOrgAdmin=membership.is_org_admin,
        businessAvailable=businessAvailable,
        departments=departmentAccessEntries,
    )
