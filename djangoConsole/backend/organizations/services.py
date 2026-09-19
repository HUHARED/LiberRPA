# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from console_project.config import LimitsConfig

from .models import (
    Department,
    DepartmentMembership,
    DepartmentRole,
    Membership,
    Organization,
)
from .permissions import (
    AccessChannel,
    require_organization_admin,
    resolve_organization_access,
)


@dataclass(frozen=True)
class OrganizationCreationResult:
    """Records created together for an authorized organization registration."""

    user: User
    organization: Organization
    membership: Membership
    general_department: Department


def _lock_organization_for_admin(
    actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> Organization:
    """Resolve and lock the current administrator context inside the caller's transaction."""
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel, forUpdate=True
    )
    require_organization_admin(access)
    return access.organization


def _get_parent_department(
    organization: Organization, parentId: uuid.UUID | None
) -> Department | None:
    if parentId is None:
        return None
    try:
        return Department.objects.get(
            pk=parentId, organization=organization, deleted_at__isnull=True
        )
    except Department.DoesNotExist:
        raise ValidationError({
            "parent": ValidationError(
                "Select an available parent department in this organization.",
                code="invalid_parent",
            )
        }) from None


def _validate_department_values(department: Department) -> None:
    # The foreign keys were resolved by the caller.
    # Reuse those objects instead of querying their existence again.
    # Constraints are checked separately before saving.
    department.full_clean(
        exclude=["organization", "parent"],
        validate_unique=False,
        validate_constraints=False,
    )


def _get_subtree_height(department: Department) -> int:
    """Count active levels, including this department, without loading unrelated branches."""
    height = 0
    levelIds = [department.pk]
    while levelIds:
        height += 1
        levelIds = list(
            Department.objects.filter(
                organization_id=department.organization_id,
                parent_id__in=levelIds,
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )
    return height


def _validate_department_depth(
    parent: Department | None,
    maxDepth: int,
    *,
    departmentId: uuid.UUID | None = None,
    subtreeHeight: int = 1,
) -> None:
    deepestDepth = subtreeHeight
    currentParent = parent
    while currentParent is not None:
        if currentParent.pk == departmentId:
            raise ValidationError({
                "parent": ValidationError(
                    "A department cannot be moved below itself or its descendants.",
                    code="department_cycle",
                )
            })
        deepestDepth += 1
        currentParent = cast(Department | None, currentParent.parent)
    if deepestDepth > maxDepth:
        raise ValidationError({
            "parent": ValidationError(
                "Departments cannot exceed %(limit)s levels.",
                code="department_depth_limit",
                params={"limit": maxDepth},
            )
        })


def _create_department(
    organization: Organization,
    *,
    name: str,
    parentId: uuid.UUID | None = None,
    notes: str = "",
) -> Department:
    """Create within the caller's transaction using a newly inserted or already locked organization."""
    parent = _get_parent_department(organization, parentId)
    department = Department(
        organization=organization, parent=parent, name=name, notes=notes
    )
    _validate_department_values(department)

    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if (
        Department.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).count()
        >= limits.maxDepartmentsPerOrganization
    ):
        raise ValidationError(
            "This organization has reached its limit of %(limit)s departments.",
            code="department_count_limit",
            params={"limit": limits.maxDepartmentsPerOrganization},
        )
    _validate_department_depth(parent, limits.maxDepartmentDepth)

    department.validate_constraints()
    department.save(force_insert=True)
    return department


@transaction.atomic
def create_department(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    name: str,
    parentId: uuid.UUID | None = None,
    notes: str = "",
) -> Department:
    """Create a department using the account and channel supplied by authentication.

    actorId and channel come from verified credentials, never from the request body.
    Operator-scoped API Keys cannot use this operation.
    """
    organization = _lock_organization_for_admin(actorId, organizationId, channel)
    return _create_department(organization, name=name, parentId=parentId, notes=notes)


@transaction.atomic
def update_department(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    departmentId: uuid.UUID,
    name: str,
    parentId: uuid.UUID | None,
    notes: str,
) -> Department:
    """Save the complete edit form using the same session contract as create_department().

    All editable values are required; parentId=None explicitly selects the root level.
    A missing, deleted, or foreign department raises Department.DoesNotExist.
    """
    organization = _lock_organization_for_admin(actorId, organizationId, channel)
    department = Department.objects.get(
        pk=departmentId, organization=organization, deleted_at__isnull=True
    )
    parent = _get_parent_department(organization, parentId)
    oldParentId = department.parent_id
    department.name = name
    department.parent = parent
    department.notes = notes
    _validate_department_values(department)

    # Editing does not consume a new slot.
    # Only a move changes subtree placement.
    # Lowering deployment limits therefore does not block name or Notes edits.
    if parentId != oldParentId:
        limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
        _validate_department_depth(
            parent,
            limits.maxDepartmentDepth,
            departmentId=departmentId,
            subtreeHeight=_get_subtree_height(department),
        )

    department.validate_constraints()
    # Update the same row and leave all identity-based relationships intact.
    department.save(update_fields=["name", "parent", "notes"])
    return department


def _prepare_department_memberships(
    membership: Membership, departmentRoles: Mapping[uuid.UUID, DepartmentRole]
) -> list[DepartmentMembership]:
    """Resolve departments in one query and validate the requested explicit roles."""
    departments = Department.objects.filter(
        organization_id=membership.organization_id, deleted_at__isnull=True
    ).in_bulk(departmentRoles)
    if len(departments) != len(departmentRoles):
        raise ValidationError({
            "department_roles": ValidationError(
                "Select available departments in this organization.",
                code="invalid_department",
            )
        })

    assignments: list[DepartmentMembership] = []
    for departmentId, role in departmentRoles.items():
        assignment = DepartmentMembership(
            membership=membership, department=departments[departmentId], role=role
        )
        # Reuse the resolved references and the model's role and organization rules.
        # Mapping keys prevent duplicate departments; the database enforces stored constraints.
        assignment.full_clean(
            exclude=["membership", "department"],
            validate_unique=False,
            validate_constraints=False,
        )
        assignments.append(assignment)
    return assignments


def _save_department_memberships(
    membership: Membership, assignments: list[DepartmentMembership]
) -> None:
    """Save validated assignments while preserving the IDs of retained relationships."""
    existingAssignments = {
        assignment.department_id: assignment
        for assignment in DepartmentMembership.objects.filter(membership=membership)
    }
    newAssignments: list[DepartmentMembership] = []
    changedAssignments: list[DepartmentMembership] = []
    for assignment in assignments:
        existing = existingAssignments.pop(assignment.department_id, None)
        if existing is None:
            newAssignments.append(assignment)
        elif existing.role != assignment.role:
            existing.role = assignment.role
            changedAssignments.append(existing)

    # Relationships left in the mapping were explicitly removed from the submitted form.
    if existingAssignments:
        DepartmentMembership.objects.filter(
            membership=membership, department_id__in=existingAssignments
        ).delete()
    DepartmentMembership.objects.bulk_update(changedAssignments, ["role"])
    DepartmentMembership.objects.bulk_create(newAssignments)


@transaction.atomic
def update_membership(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
    isOrgAdmin: bool,
    departmentRoles: Mapping[uuid.UUID, DepartmentRole],
    notes: str,
) -> Membership:
    """Save the complete member edit form using the same session contract as create_department().

    userId identifies the member being edited; actorId identifies the acting administrator.
    departmentRoles contains the complete explicit role mapping, including roles hidden by OrgAdmin.
    An empty mapping explicitly removes every department role.
    A missing or foreign membership raises Membership.DoesNotExist.
    """
    organization = _lock_organization_for_admin(actorId, organizationId, channel)
    membership = (
        Membership.objects
        .select_related("user")
        .select_for_update(of=("self", "user"))
        .get(user_id=userId, organization=organization)
    )
    wasOrgAdmin = membership.is_org_admin
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
        wasOrgAdmin
        and not membership.is_org_admin
        and not Membership.objects
        .filter(organization=organization, is_org_admin=True, user__is_active=True)
        .exclude(pk=membership.pk)
        .exists()
    ):
        raise ValidationError({
            "is_org_admin": ValidationError(
                "The organization must retain at least one active administrator.",
                code="last_org_admin",
            )
        })

    assignments = _prepare_department_memberships(membership, departmentRoles)
    membership.save(update_fields=["is_org_admin", "notes"])
    _save_department_memberships(membership, assignments)
    return membership


@sensitive_variables()
@transaction.atomic
def create_organization_records(
    *,
    verifiedEmail: str,
    password: str,
    organizationName: str,
    username: str = "",
) -> OrganizationCreationResult:
    """Create the records for an organization registration already authorized by the caller.

    The registration entry point must verify and lock the email proof, check current creation policy, and consume the proof in the same outer transaction.
    verifiedEmail must come from that proof, never from an independently editable form field.
    This internal creation step does not verify email ownership or open a login session.
    """
    # UserManager supports internal accounts without passwords, but registration requires one.
    if password is None:
        raise ValidationError({"password": "A password is required."})

    organization = Organization(name=organizationName.strip())
    organization.full_clean(validate_unique=False, validate_constraints=False)

    # Display names are not unique, so a generated name needs no availability query.
    displayName = (
        username
        if username and not username.isspace()
        else f"User {uuid.uuid4().hex[:8]}"
    )
    user = User.objects.create_user(verifiedEmail, password, username=displayName)
    organization.save(force_insert=True)
    membership = Membership(user=user, organization=organization, is_org_admin=True)
    membership.save(force_insert=True)

    # The new organization is private to this transaction until it commits.
    # General follows the same validation and quota rules as any other department.
    department = _create_department(
        organization,
        name="General",
        notes="Created automatically during organization setup.",
    )
    return OrganizationCreationResult(
        user=user,
        organization=organization,
        membership=membership,
        general_department=department,
    )
