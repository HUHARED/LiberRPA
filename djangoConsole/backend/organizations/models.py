# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .validators import validate_path_segment


class Organization(models.Model):
    """Organization identity; names may repeat across organizations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    """The account's current organization and organization-level administrator role."""

    # Django creates these attributes from the relationship fields below.
    user_id: uuid.UUID
    organization_id: uuid.UUID

    # The account ID also identifies its single current membership.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="membership",
    )
    # Organization deletion must first handle its accounts through the cleanup flow.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    is_org_admin = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    joined_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self) -> str:
        return f"User {self.user_id} in organization {self.organization_id}"


class Department(models.Model):
    """Department identity and parent link; deleted rows retain their historical IDs."""

    # Django creates these attributes from the relationship fields below.
    organization_id: uuid.UUID
    parent_id: uuid.UUID | None

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="departments",
    )
    parent: "models.ForeignKey[Department | None]" = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=128, validators=[validate_path_segment])
    notes = models.TextField(
        blank=True, default="", validators=[MaxLengthValidator(2000)]
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(parent__isnull=True)
                | ~models.Q(id=models.F("parent")),
                name="department_parent_not_self",
                violation_error_message="A department cannot be its own parent.",
            ),
            # A nullable parent needs a separate rule for names at the root level.
            models.UniqueConstraint(
                "organization",
                Lower("name"),
                condition=models.Q(parent__isnull=True, deleted_at__isnull=True),
                name="department_root_name_unique",
                violation_error_code="duplicate_department_name",
                violation_error_message="A department with this name already exists at this level.",
            ),
            models.UniqueConstraint(
                "parent",
                Lower("name"),
                condition=models.Q(parent__isnull=False, deleted_at__isnull=True),
                name="department_child_name_unique",
                violation_error_code="duplicate_department_name",
                violation_error_message="A department with this name already exists at this level.",
            ),
        ]

    def clean(self) -> None:
        """Check the direct parent; the write service handles tree-wide rules and locks."""
        super().clean()
        if self.parent_id is None:
            return
        if self.parent_id == self.pk:
            raise ValidationError({"parent": "A department cannot be its own parent."})

        try:
            # A non-null parent_id resolves to a Department or raises DoesNotExist.
            parent = cast(Department, self.parent)
        except Department.DoesNotExist:
            # full_clean() reports a missing reference during field validation.
            return
        if parent.organization_id != self.organization_id:
            raise ValidationError({
                "parent": "The parent department must belong to the same organization."
            })
        if self.deleted_at is None and parent.deleted_at is not None:
            raise ValidationError({"parent": "The parent department has been deleted."})

    def __str__(self) -> str:
        return self.name


class DepartmentRole(models.TextChoices):
    """The two roles that can be explicitly assigned within a department."""

    DEVELOPER = "developer", "Developer"
    OPERATOR = "operator", "Operator"


class DepartmentMembership(models.Model):
    """An explicit department role for a current organization member."""

    # Django creates these attributes from the relationship fields below.
    membership_id: uuid.UUID
    department_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Removing an organization membership also removes its explicit department roles.
    membership: "models.ForeignKey[Membership]" = models.ForeignKey(
        Membership,
        on_delete=models.CASCADE,
        related_name="department_memberships",
    )
    department: "models.ForeignKey[Department]" = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    # OrgAdmin stays on Membership and does not require a role in each department.
    role = models.CharField(max_length=9, choices=DepartmentRole.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "department"],
                name="department_membership_unique",
                violation_error_code="duplicate_department_membership",
                violation_error_message="This member already has a role in this department.",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=DepartmentRole.values),
                name="department_membership_role_valid",
                violation_error_code="invalid_department_role",
                violation_error_message="Select Developer or Operator.",
            ),
        ]

    def clean(self) -> None:
        """Require an active department in the member's current organization."""
        super().clean()
        try:
            membership = self.membership
            department = self.department
        except (Membership.DoesNotExist, Department.DoesNotExist):
            # full_clean() reports missing references during field validation.
            return
        if membership.organization_id != department.organization_id:
            raise ValidationError({
                "department": ValidationError(
                    "The department must belong to the member's organization.",
                    code="department_organization_mismatch",
                )
            })
        if department.deleted_at is not None:
            raise ValidationError({
                "department": ValidationError(
                    "The department has been deleted.",
                    code="invalid_department",
                )
            })

    def __str__(self) -> str:
        return (
            f"Member {self.membership_id} in department {self.department_id}: {self.role}"
        )
