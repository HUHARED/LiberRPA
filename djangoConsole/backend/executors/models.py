# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    ProhibitNullCharactersValidator,
    RegexValidator,
)
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils import timezone


class Executor(models.Model):
    """A logical execution record in one fixed department, independent of any client session."""

    department_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, related_name="executors"
    )
    name = models.CharField(
        max_length=128,
        validators=[
            RegexValidator(
                regex=r"^[^\x00-\x1f\x7f-\x9f]+$",
                message="The name must not contain control characters.",
            )
        ],
    )
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
    dispatch_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "department",
                Lower("name"),
                condition=models.Q(deleted_at__isnull=True),
                name="executor_department_name_unique",
                violation_error_code="duplicate_executor_name",
                violation_error_message="An executor with this name already exists in this department.",
            ),
            models.CheckConstraint(
                condition=models.Q(name=Trim("name")) & ~models.Q(name=""),
                name="executor_name_trimmed_nonempty",
                violation_error_message="The executor name must not be blank or have surrounding spaces.",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ExecutorSession(models.Model):
    """One account login, limited to selection until it owns one logical Executor."""

    user_id: uuid.UUID
    organization_id: uuid.UUID
    executor_id: uuid.UUID | None

    # NOTE: get_executor_sessions() adds this permission result when reading the model.
    can_use_department: bool

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="executor_sessions",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="executor_sessions",
    )
    executor = models.OneToOneField(
        Executor,
        on_delete=models.CASCADE,
        related_name="client_session",
        null=True,
        blank=True,
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    auth_hash = models.CharField(max_length=64, editable=False)
    computer = models.CharField(
        max_length=128,
        validators=[
            RegexValidator(
                r"^[^\x00-\x1f\x7f-\x9f]+$", "Use a single-line computer name."
            )
        ],
    )
    client_version = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                r"^[^\x00-\x1f\x7f-\x9f]+$", "Use a single-line client version."
            )
        ],
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    associated_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_seen_at = models.DateTimeField(null=True, blank=True, editable=False)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="executor_session_expiry_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        executor__isnull=True,
                        associated_at__isnull=True,
                        last_seen_at__isnull=True,
                    )
                    | models.Q(
                        executor__isnull=False,
                        associated_at__isnull=False,
                        last_seen_at__isnull=False,
                    )
                ),
                name="executor_session_state_valid",
            ),
        ]


class ExecutorGroup(models.Model):
    """A fixed-department target whose current members are logical Executor records."""

    department_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        related_name="executor_groups",
    )
    name = models.CharField(
        max_length=128,
        validators=[
            RegexValidator(
                regex=r"^[^\x00-\x1f\x7f-\x9f]+$",
                message="The name must not contain control characters.",
            )
        ],
    )
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "department",
                Lower("name"),
                condition=models.Q(deleted_at__isnull=True),
                name="executor_group_name_unique",
                violation_error_code="duplicate_executor_group_name",
                violation_error_message="An Executor group with this name already exists in this department.",
            ),
            models.CheckConstraint(
                condition=models.Q(name=Trim("name")) & ~models.Q(name=""),
                name="executor_group_name_valid",
                violation_error_message="The group name must not be blank or have surrounding spaces.",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ExecutorGroupMember(models.Model):
    """A current group membership, independent of client credentials and online state."""

    group_id: uuid.UUID
    executor_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        ExecutorGroup, on_delete=models.CASCADE, related_name="memberships"
    )
    executor = models.ForeignKey(
        Executor, on_delete=models.PROTECT, related_name="group_memberships"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "executor"], name="executor_group_member_unique"
            ),
        ]

    def clean(self) -> None:
        """Check a single membership; batch writes validate once under the organization lock."""
        super().clean()
        try:
            group = self.group
            executor = self.executor
        except (ExecutorGroup.DoesNotExist, Executor.DoesNotExist):
            return
        if group.department_id != executor.department_id:
            raise ValidationError({
                "executor": "Group members must belong to the group's department."
            })
        if group.deleted_at is not None or executor.deleted_at is not None:
            raise ValidationError(
                "Deleted groups and Executors cannot have current memberships."
            )
