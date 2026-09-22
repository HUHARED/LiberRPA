# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

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
