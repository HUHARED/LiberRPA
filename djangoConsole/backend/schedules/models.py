# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.conf import settings as djangoSettings
from django.db import models
from django.db.models.functions import Lower
from django.db.models.lookups import Exact
from django.utils import timezone

from packages.models import RunSettingsModel


class TriggerStatus(models.TextChoices):
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    MISSED = "missed", "Missed"


class Schedule(RunSettingsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department_id: uuid.UUID
    department = models.ForeignKey("organizations.Department", on_delete=models.PROTECT)
    package_id: uuid.UUID
    package = models.ForeignKey("packages.Package", on_delete=models.PROTECT)
    name = models.CharField(max_length=128)
    notes = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=True)
    executor_ids = models.JSONField(default=list)
    group_id = models.UUIDField(null=True, blank=True)
    cron = models.CharField(max_length=200)
    time_zone = models.CharField(max_length=100)
    active_from = models.DateTimeField()
    active_until = models.DateTimeField()
    next_trigger_at = models.DateTimeField(null=True, blank=True)
    created_by_id: uuid.UUID | None
    created_by = models.ForeignKey(
        djangoSettings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["enabled", "next_trigger_at"], name="schedule_due_idx")
        ]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "department",
                name="schedule_department_name_unique",
                violation_error_message="A Schedule with this name already exists in this department.",
            ),
            models.CheckConstraint(
                condition=models.Q(active_until__gt=models.F("active_from")),
                name="schedule_interval_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(name=""), name="schedule_name_not_empty"
            ),
            *RunSettingsModel.Meta.constraints,
            models.CheckConstraint(
                condition=Exact(
                    models.Func(
                        models.F("executor_ids"),
                        function="jsonb_typeof",
                        output_field=models.CharField(),
                    ),
                    models.Value("array"),
                ),
                name="schedule_executor_ids_array",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(group_id__isnull=False, executor_ids=[])
                    | (models.Q(group_id__isnull=True) & ~models.Q(executor_ids=[]))
                ),
                name="schedule_target_valid",
            ),
        ]


class ScheduleTrigger(models.Model):
    """A bounded trigger receipt, including failures which never started a Run."""

    organization_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    schedule_id = models.UUIDField()
    scheduled_at = models.DateTimeField()
    recorded_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=max(len(value) for value in TriggerStatus.values),
        choices=TriggerStatus.choices,
    )
    reason = models.CharField(max_length=1000, blank=True, default="")
    job_request_id = models.UUIDField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["recorded_at"], name="schedule_trigger_cleanup_idx")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule_id", "scheduled_at"], name="schedule_trigger_once"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=TriggerStatus.values),
                name="schedule_trigger_status_valid",
            ),
        ]


class SchedulerState(models.Model):
    """Committed scan boundary; only the exclusively locked scheduler advances it."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    scanned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="scheduler_state_singleton"
            )
        ]
