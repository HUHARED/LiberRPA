# FileName: backup_models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import models
from django.utils import timezone

from .backup_contracts import BackupStage, BackupSource, BackupStatus, BackupWorkerStatus


class BackupState(models.Model):
    """The worker's latest report, daily schedule cursor, and current failure notice window."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    last_schedule_at = models.DateTimeField(null=True)
    worker_status = models.CharField(
        max_length=max(len(value) for value in BackupWorkerStatus.values),
        choices=BackupWorkerStatus.choices,
        default=BackupWorkerStatus.STOPPED,
    )
    worker_checked_at = models.DateTimeField(null=True)
    failure_started_at = models.DateTimeField(null=True)
    failure_notice_at = models.DateTimeField(null=True)
    failure_message = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="backup_state_singleton"),
            models.CheckConstraint(
                condition=models.Q(worker_status__in=BackupWorkerStatus.values),
                name="backup_worker_status_valid",
            ),
        ]


class BackupRecord(models.Model):
    """One backup attempt; successful rows identify complete retained directories."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(
        max_length=max(len(value) for value in BackupSource.values),
        choices=BackupSource.choices,
    )
    scheduled_at = models.DateTimeField(null=True)
    status = models.CharField(
        max_length=max(len(value) for value in BackupStatus.values),
        choices=BackupStatus.choices,
        default=BackupStatus.PENDING,
    )
    stage = models.CharField(
        max_length=max(len(value) for value in BackupStage.values),
        choices=BackupStage.choices,
        null=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)
    data_as_of = models.DateTimeField(null=True)
    size_bytes = models.PositiveBigIntegerField(null=True)
    details = models.CharField(max_length=500, blank=True)
    cleanup_error = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source__in=BackupSource.values),
                name="backup_source_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=BackupStatus.values),
                name="backup_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(stage__isnull=True)
                | models.Q(stage__in=BackupStage.values),
                name="backup_stage_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(source=BackupSource.MANUAL, scheduled_at__isnull=True)
                | models.Q(source=BackupSource.SCHEDULED, scheduled_at__isnull=False),
                name="backup_schedule_matches_source",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status=BackupStatus.PENDING,
                    started_at__isnull=True,
                    ended_at__isnull=True,
                )
                | models.Q(
                    status=BackupStatus.RUNNING,
                    started_at__isnull=False,
                    ended_at__isnull=True,
                )
                | models.Q(
                    status__in=(BackupStatus.SUCCEEDED, BackupStatus.FAILED),
                    started_at__isnull=False,
                    ended_at__isnull=False,
                )
                | models.Q(
                    status=BackupStatus.SKIPPED,
                    started_at__isnull=True,
                    ended_at__isnull=False,
                ),
                name="backup_times_match_status",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=BackupStatus.SUCCEEDED)
                | models.Q(data_as_of__isnull=False, size_bytes__isnull=False),
                name="backup_success_has_result",
            ),
            models.UniqueConstraint(
                models.Value(1),
                condition=models.Q(status__in=(BackupStatus.PENDING, BackupStatus.RUNNING)),
                name="one_active_console_backup",
            ),
        ]
        indexes = [models.Index(fields=["status", "-ended_at"], name="backup_status_ended")]

    def __str__(self) -> str:
        return "Console backup"
