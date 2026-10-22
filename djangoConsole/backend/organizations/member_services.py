# FileName: member_services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Mapping

from django.core.exceptions import ValidationError

from executors.session_state import revoke_unqualified_executor_sessions
from operations.audit_contracts import AuditAction
from operations.audit import get_audit_snapshot, record_audit
from runs.services import recheck_job_source_access

from .contracts import DepartmentRole
from .models import Membership, Department, DepartmentMembership
from .permissions import (
    OrganizationAccessContext,
    require_organization_admin,
    has_other_active_organization_admin,
)


def _prepare_department_memberships(
    membership: Membership, departmentRoles: Mapping[uuid.UUID, DepartmentRole]
) -> list[DepartmentMembership]:
    """Resolve departments in one query and validate the requested explicit roles."""
    dictDepartmentById = Department.objects.filter(
        organization_id=membership.organization_id, deleted_at__isnull=True
    ).in_bulk(departmentRoles)
    if len(dictDepartmentById) != len(departmentRoles):
        raise ValidationError({
            "department_roles": ValidationError(
                "Select available departments in this organization.",
                code="invalid_department",
            )
        })

    listDepartmentMembership: list[DepartmentMembership] = []
    for departmentId, role in departmentRoles.items():
        departmentMembership = DepartmentMembership(
            membership=membership, department=dictDepartmentById[departmentId], role=role
        )
        # Reuse the resolved references and the model's role and organization rules.
        # Mapping keys prevent duplicate departments; the database enforces stored constraints.
        departmentMembership.full_clean(
            exclude=["membership", "department"],
            validate_unique=False,
            validate_constraints=False,
        )
        listDepartmentMembership.append(departmentMembership)
    return listDepartmentMembership


def _save_department_memberships(
    membership: Membership, departmentMemberships: list[DepartmentMembership]
) -> None:
    """Save validated assignments while preserving the IDs of retained relationships."""
    dictExistingMembershipByDepartmentId = {
        departmentMembership.department_id: departmentMembership
        for departmentMembership in DepartmentMembership.objects.filter(
            membership=membership
        )
    }
    listNewDepartmentMembership: list[DepartmentMembership] = []
    listChangedDepartmentMembership: list[DepartmentMembership] = []
    for departmentMembership in departmentMemberships:
        existingDepartmentMembership = dictExistingMembershipByDepartmentId.pop(
            departmentMembership.department_id, None
        )
        if existingDepartmentMembership is None:
            listNewDepartmentMembership.append(departmentMembership)
        elif existingDepartmentMembership.role != departmentMembership.role:
            existingDepartmentMembership.role = departmentMembership.role
            listChangedDepartmentMembership.append(existingDepartmentMembership)

    # Relationships left in the mapping were explicitly removed from the submitted form.
    if dictExistingMembershipByDepartmentId:
        DepartmentMembership.objects.filter(
            membership=membership, department_id__in=dictExistingMembershipByDepartmentId
        ).delete()
    DepartmentMembership.objects.bulk_update(listChangedDepartmentMembership, ["role"])
    DepartmentMembership.objects.bulk_create(listNewDepartmentMembership)


def update_membership(
    *,
    access: OrganizationAccessContext,
    userId: uuid.UUID,
    isOrgAdmin: bool,
    departmentRoles: Mapping[uuid.UUID, DepartmentRole],
    notes: str,
) -> Membership:
    """Save member settings using rechecked access in the caller's write transaction.

    userId identifies the member being edited; access identifies the acting administrator.
    departmentRoles contains the complete explicit role mapping, including roles hidden by OrgAdmin.
    An empty mapping explicitly removes every department role.
    A missing or foreign membership raises Membership.DoesNotExist.
    """
    require_organization_admin(access)
    organization = access.organization
    membership = (
        Membership.objects
        .select_related("user")
        .select_for_update(of=("self", "user"))
        .get(user_id=userId, organization=organization)
    )
    boolOrgAdminBefore = membership.is_org_admin
    dictAuditBefore = get_audit_snapshot(membership)
    membership.is_org_admin = isOrgAdmin
    membership.notes = notes
    membership.full_clean(
        exclude=["user", "organization"],
        validate_unique=False,
        validate_constraints=False,
    )

    # The organization lock makes competing demotions observe the preceding commit.
    # Only active accounts count; being signed in or online is not required.
    if (
        boolOrgAdminBefore
        and not membership.is_org_admin
        and not has_other_active_organization_admin(
            organizationId=organization.id, userId=membership.user_id
        )
    ):
        raise ValidationError({
            "is_org_admin": ValidationError(
                "The organization must retain at least one active administrator.",
                code="last_org_admin",
            )
        })

    listDepartmentMembership = _prepare_department_memberships(
        membership, departmentRoles
    )
    membership.save(update_fields=["is_org_admin", "notes"])
    _save_department_memberships(membership, listDepartmentMembership)
    recheck_job_source_access(membership.user_id, organization.id)
    revoke_unqualified_executor_sessions(membership.user_id, organization.id)
    record_audit(
        AuditAction.MEMBERSHIP_UPDATE,
        actor=access.actor,
        organization=organization,
        target=membership,
        channel=access.channel,
        before=dictAuditBefore,
    )
    return membership
