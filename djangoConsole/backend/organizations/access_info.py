# FileName: access_info.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from typing import cast

from accounts.models import User

from .department_queries import get_department_path
from .contracts import (
    DepartmentRole,
    OrganizationAccessResponse,
    DepartmentAccessResponse,
    AccountAccessResponse,
)
from .models import Department, Organization
from .permissions import (
    AccessChannel,
    OrganizationAccessContext,
    is_organization_business_available,
    get_current_membership,
    get_authorized_departments,
)


@dataclass(frozen=True)
class DepartmentAccessInfo:
    id: uuid.UUID
    name: str
    path: str
    # A web OrgAdmin has no department role; an API key always has the Operator role.
    role: DepartmentRole | None


def get_department_access_info(
    access: OrganizationAccessContext,
) -> tuple[DepartmentAccessInfo, ...]:
    """Describe current department scope with the credential's effective roles."""
    departmentQuery = get_authorized_departments(
        access, requiredRole=DepartmentRole.OPERATOR
    )
    dictRoleByDepartmentId: dict[uuid.UUID, DepartmentRole | None]
    if access.channel == AccessChannel.API_KEY:
        dictRoleByDepartmentId = dict.fromkeys(
            departmentQuery.values_list("id", flat=True), DepartmentRole.OPERATOR
        )
    elif access.isOrgAdmin:
        dictRoleByDepartmentId = dict.fromkeys(
            departmentQuery.values_list("id", flat=True)
        )
    else:
        # Reuse the membership join already scoped by get_authorized_departments().
        dictRoleByDepartmentId = {
            departmentId: DepartmentRole(strRole)
            for departmentId, strRole in departmentQuery.values_list(
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
            path=get_department_path(department, dictDepartmentById),
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


def get_account_access_info(*, actorId: uuid.UUID) -> AccountAccessResponse:
    """Describe the authenticated account's organization and currently available departments.

    Frozen organizations expose identity and service state for their restricted status page.
    No organization or department permissions are stored in the login session.
    """
    membership = get_current_membership(actorId=actorId)
    organization = cast(Organization, membership.organization)
    boolBusinessAvailable = is_organization_business_available(organization)
    departmentAccessEntries: tuple[DepartmentAccessInfo, ...] = ()
    if boolBusinessAvailable:
        access = OrganizationAccessContext(
            actor=cast(User, membership.user),
            organization=organization,
            isOrgAdmin=membership.is_org_admin,
            channel=AccessChannel.SESSION,
        )
        departmentAccessEntries = get_department_access_info(access)

    return AccountAccessResponse(
        organization=OrganizationAccessResponse(
            id=organization.pk,
            name=organization.name,
            suspended_at=organization.suspended_at,
            deletion_requested_at=organization.deletion_requested_at,
            deletion_due_at=organization.deletion_due_at,
            deletion_started_at=organization.deletion_started_at,
        ),
        is_org_admin=membership.is_org_admin,
        business_available=boolBusinessAvailable,
        departments=[
            DepartmentAccessResponse(
                id=departmentAccessInfo.id,
                name=departmentAccessInfo.name,
                path=departmentAccessInfo.path,
                role=departmentAccessInfo.role,
            )
            for departmentAccessInfo in departmentAccessEntries
        ],
    )
