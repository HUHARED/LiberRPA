# FileName: backup_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from console_project.logging import get_exception_summary
from console_project.recovery import is_restored_service_pending_review
from notifications.models import EmailType, EmailDelivery

from .contracts import AuditAction, AuditResult, InstanceHealthStatus
from .models import AuditScope
from .audit import record_audit
from .backup_contracts import (
    BackupStage,
    BackupSource,
    BackupStatus,
    BackupWorkerStatus,
    BackupRecordResponse,
    BackupStatusResponse,
)
from .backup_models import BackupState, BackupRecord
from .backup import BackupError, create_backup, verify_backup

_LOGGER = logging.getLogger("console.backup")
INT_BACKUP_RETENTION_COUNT = 7
INT_BACKUP_WORKER_REPORT_SECONDS = 30
INT_BACKUP_WORKER_MAX_AGE_SECONDS = 2 * INT_BACKUP_WORKER_REPORT_SECONDS
_TUPLE_ACTIVE_STATUS = (BackupStatus.PENDING, BackupStatus.RUNNING)


def get_backup_location() -> Path:
    if settings.CONSOLE_BACKUP is None:
        raise ValidationError("Backups are not configured.", code="backup_not_configured")
    return (
        Path(settings.CONSOLE_CONFIG_PATH).parent / settings.CONSOLE_BACKUP.location
    ).resolve()


def _get_due_time(currentTime: datetime) -> datetime:
    localTime = timezone.localtime(currentTime, timezone.get_default_timezone())
    intHour, intMinute = map(int, settings.CONSOLE_BACKUP.dailyTime.split(":"))
    dueAt = localTime.replace(hour=intHour, minute=intMinute, second=0, microsecond=0)
    if dueAt > localTime:
        dueAt -= timedelta(days=1)
    return dueAt


def _lock_backup_state() -> BackupState:
    state, _ = BackupState.objects.select_for_update().get_or_create(pk=1)
    return state


def _record_problem(state: BackupState, message: str, currentTime: datetime) -> None:
    if message:
        if state.failure_started_at is None:
            state.failure_started_at = currentTime
        state.failure_message = message
        if (
            state.failure_notice_at is None
            or currentTime >= state.failure_notice_at + timedelta(hours=24)
        ):
            EmailDelivery.objects.create(
                email_type=EmailType.BACKUP_FAILURE_NOTICE,
                recipient=settings.CONSOLE_BACKUP.notificationEmail.lower(),
            )
            state.failure_notice_at = currentTime
    elif state.failure_started_at is not None:
        EmailDelivery.objects.create(
            email_type=EmailType.BACKUP_RECOVERY_NOTICE,
            recipient=settings.CONSOLE_BACKUP.notificationEmail.lower(),
        )
        state.failure_started_at = None
        state.failure_notice_at = None
        state.failure_message = ""
    state.save(
        update_fields=["failure_started_at", "failure_notice_at", "failure_message"]
    )


def _prune_result_records() -> None:
    # Successful rows remain until their directory was safely removed; failures and skips need only their latest result.
    for status in (BackupStatus.FAILED, BackupStatus.SKIPPED):
        records = BackupRecord.objects.filter(status=status).order_by("-ended_at", "-id")
        latestId = records.values_list("id", flat=True).first()
        if latestId is not None:
            records.exclude(pk=latestId).delete()


def _prune_successful_backups() -> str:
    """Run only after a new complete backup, while the worker owns its host file lock."""
    pathRoot = get_backup_location()
    listOldId = list(
        BackupRecord.objects
        .filter(status=BackupStatus.SUCCEEDED)
        .order_by("-ended_at", "-id")
        .values_list("id", flat=True)[INT_BACKUP_RETENTION_COUNT:]
    )
    boolFailed = False
    for backupId in listOldId:
        try:
            pathBackup = pathRoot / backupId.hex
            if pathBackup.exists():
                shutil.rmtree(pathBackup)
        except OSError:
            boolFailed = True
            _LOGGER.warning(
                "Old backup removal failed: backup=%s.", backupId, exc_info=True
            )
            continue
        BackupRecord.objects.filter(pk=backupId, status=BackupStatus.SUCCEEDED).delete()
    return "Some older backups could not be removed." if boolFailed else ""


def report_backup_worker(status: BackupWorkerStatus) -> None:
    BackupState.objects.update_or_create(
        pk=1,
        defaults={"worker_status": status, "worker_checked_at": timezone.now()},
    )


def _finish_backup(record: BackupRecord, *, succeeded: bool, message: str) -> None:
    with transaction.atomic():
        state = _lock_backup_state()
        record.status = BackupStatus.SUCCEEDED if succeeded else BackupStatus.FAILED
        record.ended_at = timezone.now()
        record.details = message[:500]
        record.save()
        record_audit(
            AuditAction.BACKUP_COMPLETE,
            actor=None,
            organization=None,
            target=record,
            scope=AuditScope.PLATFORM,
            result=AuditResult.SUCCEEDED if succeeded else AuditResult.FAILED,
            metadata={"reason": record.details} if not succeeded else None,
        )
        # Keep an older fault open until successful retention has also completed.
        if not succeeded:
            _record_problem(state, record.details, record.ended_at)
    if succeeded:
        strCleanupError = _prune_successful_backups()
        with transaction.atomic():
            state = _lock_backup_state()
            BackupRecord.objects.filter(pk=record.id).update(
                cleanup_error=strCleanupError
            )
            _record_problem(state, strCleanupError, timezone.now())
    _prune_result_records()


def recover_interrupted_backups() -> None:
    """Call only after acquiring the exclusive host worker lock; an old process is no longer copying."""
    if is_restored_service_pending_review():
        return
    for record in BackupRecord.objects.filter(status=BackupStatus.RUNNING):
        pathBackup = get_backup_location() / record.id.hex
        try:
            if pathBackup.is_dir():
                manifest = verify_backup(pathBackup)
                if manifest.backup_id != record.id:
                    raise ValueError("The completed backup has a different identity.")
                record.data_as_of = manifest.data_as_of
                record.size_bytes = (
                    sum(entry.size_bytes for entry in manifest.files)
                    + (pathBackup / "manifest.json").stat().st_size
                )
                _finish_backup(
                    record,
                    succeeded=True,
                    message="The completed backup was verified after a worker restart.",
                )
                continue
        except DatabaseError:
            raise
        except Exception:
            _LOGGER.warning(
                "Interrupted backup verification failed: backup=%s.",
                record.id,
                exc_info=True,
            )
        pathPartial = get_backup_location() / (record.id.hex + ".partial")
        try:
            if pathPartial.exists():
                shutil.rmtree(pathPartial)
        except OSError:
            _LOGGER.warning(
                "Interrupted backup cleanup failed: backup=%s.", record.id, exc_info=True
            )
        _finish_backup(
            record,
            succeeded=False,
            message="The backup worker stopped before completion.",
        )


def schedule_due_backup() -> None:
    if settings.CONSOLE_BACKUP is None or is_restored_service_pending_review():
        return
    currentTime = timezone.now()
    dueAt = _get_due_time(currentTime)
    with transaction.atomic():
        state = _lock_backup_state()
        if state.failure_started_at is not None and (
            state.failure_notice_at is None
            or currentTime >= state.failure_notice_at + timedelta(hours=24)
        ):
            _record_problem(state, state.failure_message, currentTime)
        if state.last_schedule_at is not None and state.last_schedule_at >= dueAt:
            return
        state.last_schedule_at = dueAt
        state.save(update_fields=["last_schedule_at"])
        # A completed newer snapshot already covers a missed schedule; do not create a duplicate backup.
        if BackupRecord.objects.filter(
            status=BackupStatus.SUCCEEDED, data_as_of__gte=dueAt
        ).exists():
            return
        boolBusy = BackupRecord.objects.filter(status__in=_TUPLE_ACTIVE_STATUS).exists()
        boolWasBusy = BackupRecord.objects.filter(
            started_at__lte=dueAt, ended_at__gte=dueAt
        ).exists()
        if boolBusy or boolWasBusy:
            BackupRecord.objects.create(
                source=BackupSource.SCHEDULED,
                scheduled_at=dueAt,
                status=BackupStatus.SKIPPED,
                ended_at=currentTime,
                details="Another backup was in progress at the scheduled time.",
            )
        else:
            BackupRecord.objects.create(source=BackupSource.SCHEDULED, scheduled_at=dueAt)
    _prune_result_records()


def process_next_backup() -> bool:
    """Run one accepted backup outside database transactions, preserving its actual final result."""
    if settings.CONSOLE_BACKUP is None or is_restored_service_pending_review():
        return False
    with transaction.atomic():
        _lock_backup_state()
        record = BackupRecord.objects.filter(status=BackupStatus.PENDING).first()
        if record is None:
            return False
        record.status = BackupStatus.RUNNING
        record.stage = BackupStage.SNAPSHOT
        record.started_at = timezone.now()
        record.save(update_fields=["status", "stage", "started_at"])

    def report_stage(stage: BackupStage, dataAsOf: datetime | None) -> None:
        BackupRecord.objects.filter(pk=record.id).update(stage=stage, data_as_of=dataAsOf)
        record.stage = stage
        report_backup_worker(BackupWorkerStatus.RUNNING)

    try:
        result = create_backup(record.id, reportStage=report_stage)
    except DatabaseError:
        # The session owns the worker lock; do not reconnect to report a database failure.
        _LOGGER.exception(
            "Backup database operation failed: backup=%s stage=%s.",
            record.id,
            record.stage,
        )
        raise
    except Exception as e:
        strMessage = (
            str(e)
            if isinstance(e, BackupError)
            else f"{get_exception_summary(e)}. Check the server backup log."
        )
        strMessage = f"{BackupStage(record.stage).label}: {strMessage}"
        _LOGGER.warning(
            "Backup creation failed: backup=%s stage=%s. %s",
            record.id,
            record.stage,
            strMessage,
            exc_info=True,
        )
        record.refresh_from_db()
        _finish_backup(record, succeeded=False, message=strMessage)
    else:
        record.refresh_from_db()
        record.data_as_of = result.dataAsOf
        record.size_bytes = result.sizeBytes
        _finish_backup(
            record,
            succeeded=True,
            message="The backup completed and passed verification.",
        )
    report_backup_worker(BackupWorkerStatus.RUNNING)
    return True


def _worker_is_available(state: BackupState | None, currentTime: datetime) -> bool:
    return (
        state is not None
        and state.worker_status == BackupWorkerStatus.RUNNING
        and state.worker_checked_at is not None
        and currentTime - timedelta(seconds=INT_BACKUP_WORKER_MAX_AGE_SECONDS)
        <= state.worker_checked_at
        <= currentTime
    )


def request_backup(state: BackupState) -> tuple[BackupRecord, bool]:
    """Call after locking BackupState and rechecking the current platform session."""
    if settings.CONSOLE_BACKUP is None:
        raise ValidationError("Backups are not configured.", code="backup_not_configured")
    if is_restored_service_pending_review():
        raise ValidationError(
            "Review the restored instance and resume service before creating backups.",
            code="restore_review_required",
        )
    record = BackupRecord.objects.filter(status__in=_TUPLE_ACTIVE_STATUS).first()
    if record is not None:
        return record, False
    if not _worker_is_available(state, timezone.now()):
        raise ValidationError(
            "The backup worker is unavailable.", code="backup_worker_unavailable"
        )
    return BackupRecord.objects.create(source=BackupSource.MANUAL), True


def load_backup_status() -> BackupStatusResponse:
    currentTime = timezone.now()
    backupConfig = settings.CONSOLE_BACKUP
    state = BackupState.objects.filter(pk=1).first()
    current = BackupRecord.objects.filter(status__in=_TUPLE_ACTIVE_STATUS).first()
    completed = BackupRecord.objects.exclude(status__in=_TUPLE_ACTIVE_STATUS).order_by(
        "-ended_at", "-id"
    )
    latest = completed.first()
    lastSuccess = completed.filter(status=BackupStatus.SUCCEEDED).first()
    boolWorkerAvailable = _worker_is_available(state, currentTime)
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
            and _get_due_time(currentTime) <= lastSuccess.data_as_of <= currentTime
        ):
            healthStatus = InstanceHealthStatus.HEALTHY
            strHealthMessage = "The backup worker is active and a current successful backup is available."
        else:
            strHealthMessage = "No successful backup covers the latest scheduled time."

    def serialize(record: BackupRecord | None) -> BackupRecordResponse | None:
        if record is None:
            return None
        return BackupRecordResponse(
            id=record.id,
            source=record.source,
            status=record.status,
            stage=record.stage,
            created_at=record.created_at,
            started_at=record.started_at,
            ended_at=record.ended_at,
            data_as_of=record.data_as_of,
            size_bytes=record.size_bytes,
            details=record.details,
            cleanup_error=record.cleanup_error,
        )

    return BackupStatusResponse(
        configured=backupConfig is not None,
        location=None if backupConfig is None else str(get_backup_location()),
        daily_time=None if backupConfig is None else backupConfig.dailyTime,
        time_zone=settings.TIME_ZONE,
        retention_count=INT_BACKUP_RETENTION_COUNT,
        current=serialize(current),
        latest_result=serialize(latest),
        last_success=serialize(lastSuccess),
        health_status=healthStatus,
        checked_at=checkedAt,
        health_message=strHealthMessage,
        can_start=not strBlockedReason,
        blocked_reason=strBlockedReason,
        updated_at=currentTime,
    )
