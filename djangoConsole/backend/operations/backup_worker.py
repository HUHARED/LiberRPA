# FileName: backup_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import shutil
from datetime import datetime, timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from console_project.logging import get_exception_summary
from console_project.recovery import is_restored_service_pending_review
from notifications.models import EmailType, EmailDelivery

from .audit_contracts import AuditAction, AuditResult
from .models import AuditScope
from .audit import record_audit
from .backup_contracts import (
    INT_BACKUP_RETENTION_COUNT,
    BackupStage,
    BackupSource,
    BackupStatus,
    TUPLE_ACTIVE_BACKUP_STATUS,
    BackupWorkerStatus,
)
from .backup_models import BackupState, BackupRecord
from .backup_jobs import get_backup_location, get_backup_due_time, lock_backup_state
from .backup import BackupError, create_backup, verify_backup

_LOGGER = logging.getLogger("console.backup")


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
                time_zone=settings.TIME_ZONE,
            )
            state.failure_notice_at = currentTime
    elif state.failure_started_at is not None:
        EmailDelivery.objects.create(
            email_type=EmailType.BACKUP_RECOVERY_NOTICE,
            recipient=settings.CONSOLE_BACKUP.notificationEmail.lower(),
            time_zone=settings.TIME_ZONE,
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
        state = lock_backup_state()
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
            state = lock_backup_state()
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
    dueAt = get_backup_due_time(currentTime)
    with transaction.atomic():
        state = lock_backup_state()
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
        boolBusy = BackupRecord.objects.filter(
            status__in=TUPLE_ACTIVE_BACKUP_STATUS
        ).exists()
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
        lock_backup_state()
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
