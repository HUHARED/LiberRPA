# FileName: instance_status.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection
from django.utils import timezone

from runs.dispatch_control import require_control_service
from schedules.models import SchedulerState
from notifications.models import EmailWorkerStatus, EmailWorkerState
from notifications.worker import INT_EMAIL_WORKER_MAX_AGE_SECONDS

from .contracts import (
    InstanceHealthStatus,
    InstanceComponent,
    InstanceComponentResponse,
    InstanceStorageResponse,
    InstanceSummaryResponse,
)

_LOGGER = logging.getLogger("console.operations")
_INT_SCHEDULE_SCAN_MAX_AGE_SECONDS = 60
_INT_STORAGE_WARNING_BYTES = 10 * 1024**3


def load_instance_summary() -> InstanceSummaryResponse:
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
                    strSchedulerMessage = "No schedule scan covers the last minute."
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

    listComponent = [
        InstanceComponentResponse(
            component=InstanceComponent.DATABASE,
            status=databaseStatus,
            checked_at=databaseCheckedAt,
            message=strDatabaseMessage,
        ),
        InstanceComponentResponse(
            component=InstanceComponent.SCHEDULER,
            status=schedulerStatus,
            checked_at=schedulerCheckedAt,
            message=strSchedulerMessage,
        ),
        InstanceComponentResponse(
            component=InstanceComponent.EMAIL,
            status=emailStatus,
            checked_at=emailCheckedAt,
            message=strEmailMessage,
        ),
    ]
    for component in (
        InstanceComponent.CLEANUP,
        InstanceComponent.BACKUP,
    ):
        listComponent.append(
            InstanceComponentResponse(
                component=component,
                status=InstanceHealthStatus.UNKNOWN,
                checked_at=None,
                message="No health check is available.",
            )
        )

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
            elif diskUsage.free < _INT_STORAGE_WARNING_BYTES:
                storageStatus = InstanceHealthStatus.WARNING
                strStorageMessage = "Free space is below 10 GiB."
            else:
                storageStatus = InstanceHealthStatus.HEALTHY
                strStorageMessage = "File storage has sufficient free space."
    except OSError as e:
        strStorageMessage = "File storage space could not be read."
        _LOGGER.warning("Instance storage check failed: %s", type(e).__name__)
    storageCheckedAt = timezone.now()

    return InstanceSummaryResponse(
        updated_at=timezone.now(),
        time_zone=settings.TIME_ZONE,
        components=listComponent,
        storage=InstanceStorageResponse(
            total_bytes=intStorageTotal,
            used_bytes=intStorageUsed,
            free_bytes=intStorageFree,
            status=storageStatus,
            checked_at=storageCheckedAt,
            message=strStorageMessage,
        ),
    )
