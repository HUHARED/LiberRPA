# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import cast

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from console_project.config import LimitsConfig

from .models import Department, Membership, Organization


def _lock_organization_for_admin(
    actorId: uuid.UUID, organizationId: uuid.UUID
) -> Organization:
    """Resolve and lock the current administrator context inside the caller's transaction."""
    try:
        # All department writes lock the organization first.
        # This serializes quota and hierarchy changes per organization, including future deletions.
        organization = Organization.objects.select_for_update().get(pk=organizationId)
        # Lock the current membership and account so revocation cannot pass this write.
        Membership.objects.select_related("user").select_for_update(
            of=("self", "user")
        ).get(
            user_id=actorId,
            organization=organization,
            is_org_admin=True,
            user__is_active=True,
        )
    except (Organization.DoesNotExist, Membership.DoesNotExist):
        raise PermissionDenied("Organization administrator access is required.") from None
    return organization


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


@transaction.atomic
def create_department(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    name: str,
    parentId: uuid.UUID | None = None,
    notes: str = "",
) -> Department:
    """Create a department using the account ID supplied by the authentication layer.

    Callers must authenticate the session and enforce its channel restrictions before
    calling this service. Operator-scoped API Keys cannot use this operation.
    """
    organization = _lock_organization_for_admin(actorId, organizationId)
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
def update_department(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    departmentId: uuid.UUID,
    name: str,
    parentId: uuid.UUID | None,
    notes: str,
) -> Department:
    """Save the complete edit form using the same session contract as create_department().

    All editable values are required; parentId=None explicitly selects the root level.
    A missing, deleted, or foreign department raises Department.DoesNotExist.
    """
    organization = _lock_organization_for_admin(actorId, organizationId)
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
    # Only a move changes subtree placement, so lowering deployment limits does not block name or Notes edits.
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
