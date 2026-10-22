# FileName: backup_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db.models import TextChoices

from .contracts import InstanceHealthStatus


class BackupStage(TextChoices):
    SNAPSHOT = "snapshot", "Preparing snapshot"
    DATABASE = "database", "Exporting database"
    FILES = "files", "Copying files"
    VERIFYING = "verifying", "Verifying backup"
    FINALIZING = "finalizing", "Completing backup"


class BackupSource(TextChoices):
    MANUAL = "manual", "Manual"
    SCHEDULED = "scheduled", "Scheduled"


class BackupStatus(TextChoices):
    PENDING = "pending", "Queued"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class BackupWorkerStatus(TextChoices):
    STARTING = "starting", "Starting"
    RUNNING = "running", "Running"
    STOPPED = "stopped", "Stopped"
    FAILED = "failed", "Failed"


@dataclass(frozen=True)
class BackupRecordInfo:
    id: UUID
    source: BackupSource
    status: BackupStatus
    stage: BackupStage | None
    createdAt: datetime
    startedAt: datetime | None
    endedAt: datetime | None
    dataAsOf: datetime | None
    sizeBytes: int | None
    details: str
    cleanupError: str


@dataclass(frozen=True)
class BackupSummary:
    configured: bool
    location: str | None
    dailyTime: str | None
    timeZone: str
    retentionCount: int
    current: BackupRecordInfo | None
    latestResult: BackupRecordInfo | None
    lastSuccess: BackupRecordInfo | None
    healthStatus: InstanceHealthStatus
    checkedAt: datetime | None
    healthMessage: str
    canStart: bool
    blockedReason: str
    updatedAt: datetime
