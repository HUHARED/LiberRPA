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


def _validate_department_depth(parent: Department | None, maxDepth: int) -> None:
    depth = 1
    currentParent = parent
    while currentParent is not None:
        depth += 1
        if depth > maxDepth:
            raise ValidationError({
                "parent": ValidationError(
                    "Departments cannot exceed %(limit)s levels.",
                    code="department_depth_limit",
                    params={"limit": maxDepth},
                )
            })
        currentParent = cast(Department | None, currentParent.parent)


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
    try:
        # All department writes must lock the organization first, including future moves and deletions. This serializes quota and hierarchy changes per org.
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

    parent: Department | None = None
    if parentId is not None:
        try:
            parent = Department.objects.get(
                pk=parentId, organization=organization, deleted_at__isnull=True
            )
        except Department.DoesNotExist:
            raise ValidationError({
                "parent": ValidationError(
                    "Select an available parent department in this organization.",
                    code="invalid_parent",
                )
            }) from None

    department = Department(
        organization=organization, parent=parent, name=name, notes=notes
    )
    # The foreign keys were resolved above. Reuse those objects instead of querying
    # their existence again. Validate constraints separately with all fields present.
    department.full_clean(
        exclude=["organization", "parent"],
        validate_unique=False,
        validate_constraints=False,
    )

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
