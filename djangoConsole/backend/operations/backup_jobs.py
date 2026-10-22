# FileName: backup_jobs.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from console_project.recovery import is_restored_service_pending_review

from .audit_contracts import AuditAction, AuditStage
from .contracts import InstanceHealthStatus
from .models import AuditScope
from .audit import record_audit
from .backup_contracts import (
    INT_BACKUP_RETENTION_COUNT,
    INT_BACKUP_WORKER_MAX_AGE_SECONDS,
    BackupStage,
    BackupSource,
    BackupStatus,
    TUPLE_ACTIVE_BACKUP_STATUS,
    BackupWorkerStatus,
    BackupRecordInfo,
    BackupSummary,
)
from .backup_models import BackupState, BackupRecord


def get_backup_location() -> Path:
    if settings.CONSOLE_BACKUP is None:
        raise ValidationError("Backups are not configured.", code="backup_not_configured")
    return (
        Path(settings.CONSOLE_CONFIG_PATH).parent / settings.CONSOLE_BACKUP.location
    ).resolve()


def get_backup_due_time(currentTime: datetime) -> datetime:
    """Return the latest daily backup time at or before the supplied time."""
    localTime = timezone.localtime(currentTime, timezone.get_default_timezone())
    intHour, intMinute = map(int, settings.CONSOLE_BACKUP.dailyTime.split(":"))
    dueAt = localTime.replace(hour=intHour, minute=intMinute, second=0, microsecond=0)
    if dueAt > localTime:
        dueAt -= timedelta(days=1)
    return dueAt


def lock_backup_state() -> BackupState:
    """Lock the singleton backup state inside the caller's transaction."""
    state, _ = BackupState.objects.select_for_update().get_or_create(pk=1)
    return state


def _is_worker_available(state: BackupState | None, currentTime: datetime) -> bool:
    return (
        state is not None
        and state.worker_status == BackupWorkerStatus.RUNNING
        and state.worker_checked_at is not None
        and currentTime - timedelta(seconds=INT_BACKUP_WORKER_MAX_AGE_SECONDS)
        <= state.worker_checked_at
        <= currentTime
    )


def request_backup() -> tuple[BackupRecord, bool]:
    """Accept one manual server request; the existing worker performs the online backup."""
    if settings.CONSOLE_BACKUP is None:
        raise ValidationError("Backups are not configured.", code="backup_not_configured")
    with transaction.atomic():
        state = lock_backup_state()
        if is_restored_service_pending_review():
            raise ValidationError(
                "Review the restored instance and resume service before creating backups.",
                code="restore_review_required",
            )
        record = BackupRecord.objects.filter(
            status__in=TUPLE_ACTIVE_BACKUP_STATUS
        ).first()
        if record is not None:
            return record, False
        if not _is_worker_available(state, timezone.now()):
            raise ValidationError(
                "The backup worker is unavailable.", code="backup_worker_unavailable"
            )
        record = BackupRecord.objects.create(source=BackupSource.MANUAL)
        record_audit(
            AuditAction.BACKUP_REQUEST,
            actor=None,
            organization=None,
            target=record,
            scope=AuditScope.PLATFORM,
            stage=AuditStage.REQUEST,
            metadata={"command": "backup request"},
        )
        return record, True


def load_backup_status() -> BackupSummary:
    currentTime = timezone.now()
    backupConfig = settings.CONSOLE_BACKUP
    state = BackupState.objects.filter(pk=1).first()
    current = BackupRecord.objects.filter(status__in=TUPLE_ACTIVE_BACKUP_STATUS).first()
    completed = BackupRecord.objects.exclude(
        status__in=TUPLE_ACTIVE_BACKUP_STATUS
    ).order_by("-ended_at", "-id")
    latest = completed.first()
    lastSuccess = completed.filter(status=BackupStatus.SUCCEEDED).first()
    boolWorkerAvailable = _is_worker_available(state, currentTime)
    boolReviewPending = is_restored_service_pending_review()
    strBlockedReason = ""
    if backupConfig is None:
        strBlockedReason = "Backups are not configured."
    elif boolReviewPending:
        strBlockedReason = (
            "Review the restored instance and resume service before creating backups."
        )
    elif current is not None:
        strBlockedReason = "A backup is already queued or in progress."
    elif not boolWorkerAvailable:
        strBlockedReason = "The backup worker is unavailable."

    healthStatus = InstanceHealthStatus.UNKNOWN
    strHealthMessage = strBlockedReason or "No successful backup is available."
    checkedAt = None if state is None else state.worker_checked_at
    if backupConfig is not None and not boolReviewPending:
        boolRecentReport = (
            state is not None
            and state.worker_checked_at is not None
            and currentTime - timedelta(seconds=INT_BACKUP_WORKER_MAX_AGE_SECONDS)
            <= state.worker_checked_at
            <= currentTime
        )
        if not boolRecentReport or state is None:
            strHealthMessage = "No recent backup worker activity is available."
        elif state.worker_status == BackupWorkerStatus.FAILED:
            healthStatus = InstanceHealthStatus.ERROR
            strHealthMessage = "Backup worker stopped after an error."
        elif state.worker_status == BackupWorkerStatus.STOPPED:
            healthStatus = InstanceHealthStatus.WARNING
            strHealthMessage = "Backup worker stopped."
        elif state.worker_status == BackupWorkerStatus.STARTING:
            strHealthMessage = "Backup worker is starting."
        elif state.failure_started_at is not None:
            healthStatus = InstanceHealthStatus.ERROR
            strHealthMessage = state.failure_message
        elif current is not None:
            healthStatus = InstanceHealthStatus.WARNING
            strHealthMessage = "A backup is queued or in progress."
        elif (
            lastSuccess is not None
            and lastSuccess.data_as_of is not None
            and get_backup_due_time(currentTime) <= lastSuccess.data_as_of <= currentTime
        ):
            healthStatus = InstanceHealthStatus.HEALTHY
            strHealthMessage = "The backup worker is active and a current successful backup is available."
        else:
            strHealthMessage = "No successful backup covers the latest scheduled time."

    def _build_record_info(record: BackupRecord | None) -> BackupRecordInfo | None:
        if record is None:
            return None
        return BackupRecordInfo(
            id=record.id,
            source=BackupSource(record.source),
            status=BackupStatus(record.status),
            stage=BackupStage(record.stage) if record.stage is not None else None,
            createdAt=record.created_at,
            startedAt=record.started_at,
            endedAt=record.ended_at,
            dataAsOf=record.data_as_of,
            sizeBytes=record.size_bytes,
            details=record.details,
            cleanupError=record.cleanup_error,
        )

    return BackupSummary(
        configured=backupConfig is not None,
        location=None if backupConfig is None else str(get_backup_location()),
        dailyTime=None if backupConfig is None else backupConfig.dailyTime,
        timeZone=settings.TIME_ZONE,
        retentionCount=INT_BACKUP_RETENTION_COUNT,
        current=_build_record_info(current),
        latestResult=_build_record_info(latest),
        lastSuccess=_build_record_info(lastSuccess),
        healthStatus=healthStatus,
        checkedAt=checkedAt,
        healthMessage=strHealthMessage,
        canStart=not strBlockedReason,
        blockedReason=strBlockedReason,
        updatedAt=currentTime,
    )
