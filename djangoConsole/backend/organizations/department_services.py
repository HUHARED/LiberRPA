# FileName: department_services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError

from console_project.config import LimitsConfig
from operations.audit import get_audit_snapshot, record_audit

from .limits import get_organization_limits
from .models import Organization, Department
from .validators import get_path_name_key, normalize_path_name
from .permissions import OrganizationAccessContext, require_organization_admin

# NOTE: Department writes require the caller's transaction through response construction.


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


def _prepare_department_values(department: Department) -> None:
    """Normalize the display name, derive its key, and validate the remaining editable fields."""
    try:
        department.name = normalize_path_name(department.name)
    except ValidationError as e:
        raise ValidationError({"name": e}) from None
    department.name_key = get_path_name_key(department.name)
    # The name and related objects are already validated; constraints are checked once before saving.
    department.full_clean(
        exclude=["name", "organization", "parent"],
        validate_unique=False,
        validate_constraints=False,
    )


def _validate_department_depth(
    parentDepartment: Department | None,
    maxDepth: int,
    *,
    departmentId: uuid.UUID | None = None,
    subtreeHeight: int = 1,
) -> None:
    intDeepestDepth = subtreeHeight
    currentParent = parentDepartment
    while currentParent is not None:
        if currentParent.pk == departmentId:
            raise ValidationError({
                "parent": ValidationError(
                    "A department cannot be moved below itself or its descendants.",
                    code="department_cycle",
                )
            })
        intDeepestDepth += 1
        currentParent = cast(Department | None, currentParent.parent)
    if intDeepestDepth > maxDepth:
        raise ValidationError({
            "parent": ValidationError(
                "Departments cannot exceed %(limit)s levels.",
                code="department_depth_limit",
                params={"limit": maxDepth},
            )
        })


def _get_department_subtree_height(department: Department) -> int:
    """Count active levels, including this department, without loading unrelated branches."""
    intSubtreeHeight = 0
    listLevelDepartmentId = [department.pk]
    while listLevelDepartmentId:
        intSubtreeHeight += 1
        listLevelDepartmentId = list(
            Department.objects.filter(
                organization_id=department.organization_id,
                parent_id__in=listLevelDepartmentId,
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )
    return intSubtreeHeight


def _create_department_record(
    organization: Organization,
    *,
    name: str,
    parentId: uuid.UUID | None = None,
    notes: str = "",
) -> Department:
    """Create within the caller's transaction using a newly inserted or already locked organization."""
    parentDepartment = _get_parent_department(organization, parentId)
    department = Department(
        organization=organization, parent=parentDepartment, name=name, notes=notes
    )
    _prepare_department_values(department)

    limits = get_organization_limits(organization)
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
    _validate_department_depth(parentDepartment, limits.maxDepartmentDepth)

    department.validate_constraints()
    department.save(force_insert=True)
    return department


def create_department(
    *,
    access: OrganizationAccessContext,
    name: str,
    parentId: uuid.UUID | None = None,
    notes: str = "",
) -> Department:
    """Create a department using rechecked access in the caller's write transaction."""
    require_organization_admin(access)
    organization = access.organization
    department = _create_department_record(
        organization, name=name, parentId=parentId, notes=notes
    )
    record_audit(
        "department.create",
        actor=access.actor,
        organization=organization,
        target=department,
        channel=access.channel,
        before={},
    )
    return department


def update_department(
    *,
    access: OrganizationAccessContext,
    departmentId: uuid.UUID,
    name: str,
    parentId: uuid.UUID | None,
    notes: str,
) -> Department:
    """Save the complete edit form using the same session contract as create_department().

    All editable values are required; parentId=None explicitly selects the root level.
    A missing, deleted, or foreign department raises Department.DoesNotExist.
    """
    require_organization_admin(access)
    organization = access.organization
    department = Department.objects.get(
        pk=departmentId, organization=organization, deleted_at__isnull=True
    )
    parentDepartment = _get_parent_department(organization, parentId)
    oldParentId = department.parent_id
    dictAuditBefore = get_audit_snapshot(department)
    department.name = name
    department.parent = parentDepartment
    department.notes = notes
    _prepare_department_values(department)

    # NOTE: Check depth only when moving; lower limits must not block name or Notes edits.
    if parentId != oldParentId:
        limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
        _validate_department_depth(
            parentDepartment,
            limits.maxDepartmentDepth,
            departmentId=departmentId,
            subtreeHeight=_get_department_subtree_height(department),
        )

    department.validate_constraints()
    # Update the same row and leave all identity-based relationships intact.
    department.save(update_fields=["name", "name_key", "parent", "notes"])
    record_audit(
        "department.update",
        actor=access.actor,
        organization=organization,
        target=department,
        channel=access.channel,
        before=dictAuditBefore,
    )
    return department


def create_general_department(organization: Organization) -> Department:
    """Create the default department inside the new organization's registration transaction."""
    return _create_department_record(
        organization,
        name="General",
        notes="Created automatically during organization setup.",
    )
