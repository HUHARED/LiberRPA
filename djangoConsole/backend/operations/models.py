# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import models
from django.utils import timezone

from console_project.constants import INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH

from .contracts import AuditChannel, AuditResult, AuditStage


class ServiceSettings(models.Model):
    """One shared settings record for the Console instance, independent of any organization."""

    # This fixed key identifies the singleton settings row, not a business resource.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    allow_organization_creation = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="service_settings_singleton",
                violation_error_message="The Console instance can have only one service settings record.",
            )
        ]

    def __str__(self) -> str:
        return "Console service settings"


class CleanupTask(models.TextChoices):
    FILE_STORAGE = "file_storage", "File Storage"
    RUN_DATA = "run_data", "Run Data"
    EMAIL_HISTORY = "email_history", "Email History"
    AUDIT_HISTORY = "audit_history", "Audit History"
    API_KEYS = "api_keys", "API Keys"


class CleanupStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class CleanupState(models.Model):
    """Latest started attempt for each routine cleanup task, without execution history."""

    task = models.CharField(
        primary_key=True,
        max_length=max(len(value) for value in CleanupTask.values),
        choices=CleanupTask.choices,
    )
    attempt_id = models.UUIDField(default=uuid.uuid4, editable=False)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(
        max_length=max(len(value) for value in CleanupStatus.values),
        choices=CleanupStatus.choices,
        default=CleanupStatus.RUNNING,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(task__in=CleanupTask.values),
                name="cleanup_task_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=CleanupStatus.values),
                name="cleanup_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status=CleanupStatus.RUNNING, finished_at__isnull=True)
                | models.Q(
                    status__in=(CleanupStatus.SUCCEEDED, CleanupStatus.FAILED),
                    finished_at__isnull=False,
                ),
                name="cleanup_finished_at_matches_status",
            ),
        ]


class AuditScope(models.TextChoices):
    ORGANIZATION = "organization", "Organization"
    PLATFORM = "platform", "Platform"


class AuditRecord(models.Model):
    """Append-only application history with snapshots, not cascading business links."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    scope = models.CharField(
        max_length=max(len(value) for value in AuditScope.values),
        choices=AuditScope,
        editable=False,
    )
    organization_id = models.UUIDField(null=True, editable=False)
    organization_name = models.CharField(max_length=200, blank=True, editable=False)
    actor_id = models.UUIDField(null=True, editable=False)
    actor_name = models.CharField(
        max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH, editable=False
    )
    channel = models.CharField(
        max_length=max(len(value) for value in AuditChannel.values),
        choices=AuditChannel,
        editable=False,
    )
    request_id = models.UUIDField(null=True, editable=False)
    module = models.CharField(max_length=32, editable=False)
    action = models.CharField(max_length=64, editable=False)
    object_type = models.CharField(max_length=64, editable=False)
    object_id = models.CharField(max_length=64, blank=True, editable=False)
    object_name = models.CharField(
        max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH, blank=True, editable=False
    )
    department_id = models.UUIDField(null=True, editable=False)
    result = models.CharField(
        max_length=max(len(value) for value in AuditResult.values),
        choices=AuditResult,
        editable=False,
    )
    # Writers allowlist metadata and bound the entire JSON document to 4 KiB.
    details = models.JSONField(default=dict, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["created_at", "id"], name="audit_retention_time_idx"),
            models.Index(
                fields=["scope", "organization_id", "-created_at", "-id"],
                name="audit_org_time_idx",
            ),
            models.Index(
                fields=["scope", "-created_at", "-id"], name="audit_scope_time_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scope__in=AuditScope.values)
                & (
                    models.Q(scope=AuditScope.PLATFORM)
                    | models.Q(organization_id__isnull=False)
                ),
                name="audit_scope_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=AuditChannel.values),
                name="audit_channel_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(result__in=AuditResult.values),
                name="audit_result_valid",
            ),
            models.CheckConstraint(
                # A missing stage means operation; an explicit value must be valid.
                condition=models.Q(details__stage__isnull=True)
                | models.Q(details__stage__in=AuditStage.values),
                name="audit_stage_valid",
            ),
        ]
