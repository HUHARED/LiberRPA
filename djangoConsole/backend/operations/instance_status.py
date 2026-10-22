# FileName: instance_status.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection
from django.utils import timezone

from console_project.version import STR_CONSOLE_VERSION
from console_project.recovery import is_restored_service_pending_review

from runs.worker_state import require_control_service
from schedules.models import SchedulerState
from notifications.models import EmailWorkerStatus, EmailWorkerState
from notifications.worker import INT_EMAIL_WORKER_MAX_AGE_SECONDS

from .contracts import ServiceState, InstanceHealthStatus, InstanceComponent
from .models import MaintenanceState, CleanupTask, CleanupStatus, CleanupState
from .cleanup_status import DICT_CLEANUP_MAX_AGE_SECONDS
from .capacity_contracts import INT_STORAGE_WARNING_BYTES
from .backup_contracts import BackupRecordInfo
from .backup_worker import load_backup_status

_LOGGER = logging.getLogger("console.operations")
_INT_SCHEDULE_SCAN_MAX_AGE_SECONDS = 60


@dataclass(frozen=True)
class InstanceComponentInfo:
    component: InstanceComponent
    status: InstanceHealthStatus
    checkedAt: datetime | None
    message: str


@dataclass(frozen=True)
class InstanceStorageInfo:
    totalBytes: int | None
    usedBytes: int | None
    freeBytes: int | None
    status: InstanceHealthStatus
    checkedAt: datetime
    message: str


@dataclass(frozen=True)
class InstanceSummary:
    version: str
    serviceState: ServiceState | None
    maintenanceEnteredAt: datetime | None
    lastSuccessfulBackup: BackupRecordInfo | None
    updatedAt: datetime
    timeZone: str
    components: list[InstanceComponentInfo]
    storage: InstanceStorageInfo


def load_instance_summary() -> InstanceSummary:
    databaseStatus = InstanceHealthStatus.HEALTHY
    strDatabaseMessage = "Database query succeeded."
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as e:
        databaseStatus = InstanceHealthStatus.ERROR
        strDatabaseMessage = "Database query failed."
        _LOGGER.warning("Instance database check failed: %s", type(e).__name__)
    databaseCheckedAt = timezone.now()

    serviceState = None
    maintenanceEnteredAt = None
    if databaseStatus == InstanceHealthStatus.HEALTHY:
        try:
            maintenance = MaintenanceState.objects.filter(pk=1).first()
            maintenanceEnteredAt = None if maintenance is None else maintenance.entered_at
            serviceState = (
                ServiceState.MAINTENANCE
                if maintenanceEnteredAt is not None
                or is_restored_service_pending_review()
                else ServiceState.NORMAL
            )
        except (DatabaseError, OSError) as e:
            _LOGGER.warning(
                "Instance maintenance state could not be read: %s", type(e).__name__
            )

    schedulerStatus = InstanceHealthStatus.UNKNOWN
    schedulerCheckedAt = None
    strSchedulerMessage = "The database check failed; scheduler status is unavailable."
    if databaseStatus == InstanceHealthStatus.HEALTHY:
        try:
            schedulerState = SchedulerState.objects.filter(pk=1).first()
            schedulerCheckedAt = (
                None if schedulerState is None else schedulerState.scanned_at
            )
            try:
                control = require_control_service(timezone.now())
            except ValidationError:
                strSchedulerMessage = "No recent run control activity is available."
            else:
                currentTime = timezone.now()
                if control.last_tick_at > currentTime:
                    strSchedulerMessage = (
                        "The run control activity time is in the future."
                    )
                elif (
                    control.recovery_until is not None
                    and control.recovery_until > currentTime
                ):
                    schedulerStatus = InstanceHealthStatus.WARNING
                    strSchedulerMessage = (
                        "Run control is recovering; schedule triggers are paused."
                    )
                elif schedulerCheckedAt is None:
                    strSchedulerMessage = "No completed schedule scan is available."
                elif schedulerCheckedAt > currentTime:
                    strSchedulerMessage = "The schedule scan time is in the future."
                elif currentTime - schedulerCheckedAt > timedelta(
                    seconds=_INT_SCHEDULE_SCAN_MAX_AGE_SECONDS
                ):
                    strSchedulerMessage = (
                        "Schedule triggers are paused for maintenance."
                        if serviceState == ServiceState.MAINTENANCE
                        else "No schedule scan covers the last minute."
                    )
                else:
                    schedulerStatus = InstanceHealthStatus.HEALTHY
                    strSchedulerMessage = (
                        "Schedule scanning and run control have recent activity."
                    )
        except DatabaseError as e:
            strSchedulerMessage = "Scheduler status could not be read."
            _LOGGER.warning("Instance scheduler check failed: %s", type(e).__name__)

    emailStatus = InstanceHealthStatus.UNKNOWN
    emailCheckedAt = None
    strEmailMessage = "The database check failed; email worker status is unavailable."
    if databaseStatus == InstanceHealthStatus.HEALTHY:
        try:
            emailWorker = EmailWorkerState.objects.filter(pk=1).first()
            currentTime = timezone.now()
            if emailWorker is None:
                strEmailMessage = "No email worker activity is available."
            else:
                emailCheckedAt = emailWorker.checked_at
                if emailCheckedAt > currentTime:
                    strEmailMessage = "The email worker activity time is in the future."
                elif currentTime - emailCheckedAt > timedelta(
                    seconds=INT_EMAIL_WORKER_MAX_AGE_SECONDS
                ):
                    strEmailMessage = "No recent email worker activity is available."
                elif emailWorker.status == EmailWorkerStatus.STARTING:
                    strEmailMessage = "Email worker is starting."
                elif emailWorker.status == EmailWorkerStatus.RUNNING:
                    emailStatus = InstanceHealthStatus.HEALTHY
                    strEmailMessage = "Email worker has recent activity."
                elif emailWorker.status == EmailWorkerStatus.STOPPED:
                    emailStatus = InstanceHealthStatus.WARNING
                    strEmailMessage = "Email worker stopped."
                elif emailWorker.status == EmailWorkerStatus.FAILED:
                    emailStatus = InstanceHealthStatus.ERROR
                    strEmailMessage = "Email worker stopped after an error."
        except DatabaseError as e:
            strEmailMessage = "Email worker status could not be read."
            _LOGGER.warning("Instance email worker check failed: %s", type(e).__name__)

    cleanupStatus = InstanceHealthStatus.UNKNOWN
    cleanupCheckedAt = None
    strCleanupMessage = "The database check failed; cleanup status is unavailable."
    if databaseStatus == InstanceHealthStatus.HEALTHY:
        try:
            dictCleanupState = {state.task: state for state in CleanupState.objects.all()}
            currentTime = timezone.now()
            dictCleanupEvidence: dict[
                InstanceHealthStatus, list[tuple[str, datetime | None]]
            ] = {status: [] for status in InstanceHealthStatus}
            for task in CleanupTask:
                cleanupState = dictCleanupState.get(task)
                if cleanupState is None:
                    dictCleanupEvidence[InstanceHealthStatus.UNKNOWN].append((
                        str(task.label),
                        None,
                    ))
                    continue
                evidenceAt = cleanupState.finished_at or cleanupState.started_at
                if (
                    cleanupState.started_at > currentTime
                    or evidenceAt > currentTime
                    or evidenceAt < cleanupState.started_at
                    or currentTime - evidenceAt
                    > timedelta(seconds=DICT_CLEANUP_MAX_AGE_SECONDS[task])
                ):
                    taskStatus = InstanceHealthStatus.UNKNOWN
                elif cleanupState.status == CleanupStatus.FAILED:
                    taskStatus = InstanceHealthStatus.ERROR
                elif cleanupState.status == CleanupStatus.RUNNING:
                    taskStatus = InstanceHealthStatus.WARNING
                else:
                    taskStatus = InstanceHealthStatus.HEALTHY
                dictCleanupEvidence[taskStatus].append((str(task.label), evidenceAt))

            for status in (
                InstanceHealthStatus.ERROR,
                InstanceHealthStatus.UNKNOWN,
                InstanceHealthStatus.WARNING,
                InstanceHealthStatus.HEALTHY,
            ):
                listEvidence = dictCleanupEvidence[status]
                if not listEvidence:
                    continue
                cleanupStatus = status
                listEvidenceTime = [checkedAt for _, checkedAt in listEvidence]
                cleanupCheckedAt = (
                    None
                    if any(checkedAt is None for checkedAt in listEvidenceTime)
                    else min(
                        checkedAt
                        for checkedAt in listEvidenceTime
                        if checkedAt is not None
                    )
                )
                strTaskNames = ", ".join(strName for strName, _ in listEvidence)
                if status == InstanceHealthStatus.ERROR:
                    strCleanupMessage = f"Cleanup failed: {strTaskNames}."
                elif status == InstanceHealthStatus.UNKNOWN:
                    strCleanupMessage = f"No recent cleanup result: {strTaskNames}."
                elif status == InstanceHealthStatus.WARNING:
                    strCleanupMessage = f"Cleanup in progress: {strTaskNames}."
                else:
                    strCleanupMessage = (
                        "Recent routine cleanup runs completed successfully."
                    )
                break
        except DatabaseError as e:
            strCleanupMessage = "Cleanup status could not be read."
            _LOGGER.warning("Instance cleanup check failed: %s", type(e).__name__)

    backupStatus = InstanceHealthStatus.UNKNOWN
    backupCheckedAt = None
    strBackupMessage = "The database check failed; backup status is unavailable."
    lastSuccessfulBackup: BackupRecordInfo | None = None
    if databaseStatus == InstanceHealthStatus.HEALTHY:
        try:
            backup = load_backup_status()
            backupStatus = backup.healthStatus
            backupCheckedAt = backup.checkedAt
            strBackupMessage = backup.healthMessage
            lastSuccess = backup.lastSuccess
            if (
                lastSuccess is not None
                and lastSuccess.endedAt is not None
                and lastSuccess.dataAsOf is not None
                and lastSuccess.sizeBytes is not None
            ):
                lastSuccessfulBackup = lastSuccess
        except (DatabaseError, OSError) as e:
            strBackupMessage = "Backup status could not be read."
            _LOGGER.warning(
                "Instance backup status could not be read: %s", type(e).__name__
            )

    listComponent = [
        InstanceComponentInfo(
            component=InstanceComponent.DATABASE,
            status=databaseStatus,
            checkedAt=databaseCheckedAt,
            message=strDatabaseMessage,
        ),
        InstanceComponentInfo(
            component=InstanceComponent.SCHEDULER,
            status=schedulerStatus,
            checkedAt=schedulerCheckedAt,
            message=strSchedulerMessage,
        ),
        InstanceComponentInfo(
            component=InstanceComponent.EMAIL,
            status=emailStatus,
            checkedAt=emailCheckedAt,
            message=strEmailMessage,
        ),
        InstanceComponentInfo(
            component=InstanceComponent.CLEANUP,
            status=cleanupStatus,
            checkedAt=cleanupCheckedAt,
            message=strCleanupMessage,
        ),
        InstanceComponentInfo(
            component=InstanceComponent.BACKUP,
            status=backupStatus,
            checkedAt=backupCheckedAt,
            message=strBackupMessage,
        ),
    ]

    intStorageTotal: int | None = None
    intStorageUsed: int | None = None
    intStorageFree: int | None = None
    storageStatus = InstanceHealthStatus.ERROR
    strStorageMessage = "The file storage directory is unavailable."
    pathStorage = Path(settings.CONSOLE_STORAGE_ROOT)
    try:
        if pathStorage.is_dir():
            diskUsage = shutil.disk_usage(pathStorage)
            intStorageTotal = diskUsage.total
            intStorageUsed = diskUsage.used
            intStorageFree = diskUsage.free
            if diskUsage.free < settings.CONSOLE_LIMITS.minStorageFreeBytes:
                strStorageMessage = (
                    "Free space is below the minimum required for file uploads."
                )
            elif diskUsage.free < INT_STORAGE_WARNING_BYTES:
                storageStatus = InstanceHealthStatus.WARNING
                strStorageMessage = "Free space is below 10 GiB."
            else:
                storageStatus = InstanceHealthStatus.HEALTHY
                strStorageMessage = "File storage has sufficient free space."
    except OSError as e:
        strStorageMessage = "File storage space could not be read."
        _LOGGER.warning("Instance storage check failed: %s", type(e).__name__)
    storageCheckedAt = timezone.now()

    return InstanceSummary(
        version=STR_CONSOLE_VERSION,
        serviceState=serviceState,
        maintenanceEnteredAt=maintenanceEnteredAt,
        lastSuccessfulBackup=lastSuccessfulBackup,
        updatedAt=timezone.now(),
        timeZone=settings.TIME_ZONE,
        components=listComponent,
        storage=InstanceStorageInfo(
            totalBytes=intStorageTotal,
            usedBytes=intStorageUsed,
            freeBytes=intStorageFree,
            status=storageStatus,
            checkedAt=storageCheckedAt,
            message=strStorageMessage,
        ),
    )
