# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import (
    MaxLengthValidator,
    MinValueValidator,
    MaxValueValidator,
    ProhibitNullCharactersValidator,
)
from django.db import models
from django.db.models.expressions import CombinedExpression
from django.db.models.functions import Lower, Trim
from django.db.models.lookups import Exact
from django.utils import timezone

from console_project.constants import INT_MAX_RUN_LOG_RETENTION_DAYS
from console_project.validators import validate_time_zone

from .contracts import DepartmentRole
from .limits import OrganizationLimit, validate_limit_overrides
from .validators import validate_path_segment


class Organization(models.Model):
    """Organization identity and service state; names may repeat across organizations."""

    # Populated by the platform organization query's administrator prefetch.
    organizationAdministrators: list["Membership"]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200, validators=[ProhibitNullCharactersValidator()]
    )
    default_time_zone = models.CharField(
        max_length=100, default="UTC", validators=[validate_time_zone]
    )
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    limit_overrides = models.JSONField(
        default=dict, blank=True, validators=[validate_limit_overrides]
    )

    run_log_retention_days = models.PositiveSmallIntegerField(
        default=INT_MAX_RUN_LOG_RETENTION_DAYS,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(INT_MAX_RUN_LOG_RETENTION_DAYS),
        ],
    )

    # Service suspension is independent of the deletion lifecycle.
    suspended_at = models.DateTimeField(null=True, blank=True, editable=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True, editable=False)
    # The due time permits cleanup but does not mean cleanup has actually started.
    deletion_due_at = models.DateTimeField(null=True, blank=True, editable=False)
    deletion_started_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        indexes = [
            models.Index(
                fields=["deletion_due_at", "id"],
                condition=models.Q(deletion_requested_at__isnull=False),
                name="organization_deletion_due_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    run_log_retention_days__gte=1,
                    run_log_retention_days__lte=INT_MAX_RUN_LOG_RETENTION_DAYS,
                ),
                name="organization_log_retention_valid",
                violation_error_message=(
                    f"Run Log Retention must be between 1 and {INT_MAX_RUN_LOG_RETENTION_DAYS} days."
                ),
            ),
            models.CheckConstraint(
                condition=Exact(
                    models.Func(
                        models.F("limit_overrides"),
                        function="jsonb_typeof",
                        output_field=models.CharField(),
                    ),
                    models.Value("object"),
                )
                & Exact(
                    CombinedExpression(
                        models.F("limit_overrides"),
                        "-",
                        models.Value(
                            OrganizationLimit.values,
                            output_field=ArrayField(models.TextField()),
                        ),
                        output_field=models.JSONField(),
                    ),
                    models.Value({}, output_field=models.JSONField()),
                ),
                name="organization_limit_overrides_valid",
                violation_error_message="Organization limits must contain only supported override keys.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        deletion_requested_at__isnull=True, deletion_due_at__isnull=True
                    )
                    | models.Q(
                        deletion_requested_at__isnull=False,
                        deletion_due_at__isnull=False,
                        deletion_due_at__gte=models.F("deletion_requested_at"),
                    )
                ),
                name="organization_deletion_schedule_valid",
                violation_error_code="invalid_deletion_schedule",
                violation_error_message="A deletion request requires a cleanup due time at or after the request time.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(deletion_started_at__isnull=True)
                    | models.Q(
                        deletion_due_at__isnull=False,
                        deletion_started_at__gte=models.F("deletion_due_at"),
                    )
                ),
                name="organization_deletion_start_valid",
                violation_error_code="invalid_deletion_start",
                violation_error_message="Deletion cleanup can only start when its scheduled due time has been reached.",
            ),
        ]

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
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
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
    # NOTE: Name writes must update this key through the business service.
    name_key = models.TextField(editable=False, db_collation="C")
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
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
                fields=["organization", "name_key"],
                condition=models.Q(parent__isnull=True, deleted_at__isnull=True),
                name="department_root_name_unique",
                violation_error_code="duplicate_department_name",
                violation_error_message="A department with this name already exists at this level.",
            ),
            models.UniqueConstraint(
                fields=["parent", "name_key"],
                condition=models.Q(parent__isnull=False, deleted_at__isnull=True),
                name="department_child_name_unique",
                violation_error_code="duplicate_department_name",
                violation_error_message="A department with this name already exists at this level.",
            ),
        ]

    def __str__(self) -> str:
        return self.name


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
    role = models.CharField(
        max_length=max(len(value) for value in DepartmentRole.values),
        choices=DepartmentRole.choices,
    )

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

    def __str__(self) -> str:
        return (
            f"Member {self.membership_id} in department {self.department_id}: {self.role}"
        )


class MemberInvitation(models.Model):
    """An immutable proposed membership with a replaceable, private registration proof."""

    organization_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="invitations"
    )
    email = models.EmailField()
    is_org_admin = models.BooleanField(default=False)
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    requested_at = models.DateTimeField(editable=False)
    expires_at = models.DateTimeField(editable=False)
    # NOTE: Each resend changes the request ID before a worker can issue its new token.
    request_id = models.UUIDField(default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, null=True, editable=False)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "email", "-requested_at"],
                name="invitation_recipient_idx",
            ),
            models.Index(
                fields=["organization", "expires_at"], name="invitation_reservation_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email=Lower(Trim("email"))) & ~models.Q(email=""),
                name="invitation_email_canonical",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("requested_at")),
                name="invitation_expiry_after_request",
            ),
            models.CheckConstraint(
                condition=models.Q(accepted_at__isnull=True)
                | models.Q(revoked_at__isnull=True),
                name="invitation_single_outcome",
            ),
        ]


class InvitationDepartmentRole(models.Model):
    """A proposed role; it grants no access until the invitation is accepted."""

    invitation_id: uuid.UUID
    department_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.ForeignKey(
        MemberInvitation, on_delete=models.CASCADE, related_name="department_roles"
    )
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    role = models.CharField(
        max_length=max(len(value) for value in DepartmentRole.values),
        choices=DepartmentRole.choices,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invitation", "department"], name="invitation_department_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=DepartmentRole.values),
                name="invitation_role_valid",
            ),
        ]
