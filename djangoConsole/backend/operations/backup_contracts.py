# FileName: backup_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field

from console_project.contracts import JsonResponsePayload

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


class BackupRecordResponse(JsonResponsePayload):
    id: UUID
    source: BackupSource = Field(strict=False)
    status: BackupStatus = Field(strict=False)
    stage: BackupStage | None = Field(strict=False)
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    data_as_of: datetime | None
    size_bytes: int | None
    details: str
    cleanup_error: str


class BackupStatusResponse(JsonResponsePayload):
    configured: bool
    location: str | None
    daily_time: str | None
    time_zone: str
    retention_count: int
    current: BackupRecordResponse | None
    latest_result: BackupRecordResponse | None
    last_success: BackupRecordResponse | None
    health_status: InstanceHealthStatus = Field(strict=False)
    checked_at: datetime | None
    health_message: str
    can_start: bool
    blocked_reason: str
    updated_at: datetime
