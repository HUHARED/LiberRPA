# FileName: run_backup_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from threading import Event

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from console_project.local_locks import LocalLockUnavailableError, hold_local_lock
from console_project.logging import get_exception_summary
from console_project.recovery import is_restored_service_pending_review
from console_project.workers import (
    BACKUP_WORKER_LOCK_ID,
    WorkerAlreadyRunningError,
    hold_worker_session,
    stop_on_signals,
)
from operations.backup_contracts import BackupWorkerStatus
from operations.backup_worker import (
    INT_BACKUP_WORKER_REPORT_SECONDS,
    get_backup_location,
    report_backup_worker,
    recover_interrupted_backups,
    schedule_due_backup,
    process_next_backup,
)

_LOGGER = logging.getLogger("console.backup")


class Command(BaseCommand):
    help = "Process manual and daily Console backups; unconfigured instances wait without starting backups."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process one due or queued backup and exit.",
        )

    def handle(self, *_args: object, **options: object) -> None:
        stopEvent = Event()
        with stop_on_signals(stopEvent):
            if settings.CONSOLE_BACKUP is None:
                self.stdout.write("Backups are not configured.")
                while not options["once"] and not stopEvent.wait(
                    INT_BACKUP_WORKER_REPORT_SECONDS
                ):
                    pass
                return
            try:
                pathRoot = get_backup_location()
                pathRoot.mkdir(mode=0o700, parents=True, exist_ok=True)
                with (
                    hold_local_lock(pathRoot / ".worker.lock"),
                    hold_worker_session(
                        lockId=BACKUP_WORKER_LOCK_ID, workerName="backup"
                    ),
                ):
                    boolStarted = False
                    try:
                        while not stopEvent.is_set():
                            if is_restored_service_pending_review():
                                if options["once"]:
                                    self.stdout.write(
                                        "Backups are paused until the restored instance is reviewed and service resumes."
                                    )
                                    break
                                stopEvent.wait(INT_BACKUP_WORKER_REPORT_SECONDS)
                                continue
                            if not boolStarted:
                                report_backup_worker(BackupWorkerStatus.STARTING)
                                recover_interrupted_backups()
                                boolStarted = True
                                _LOGGER.info("Backup worker started.")
                            report_backup_worker(BackupWorkerStatus.RUNNING)
                            schedule_due_backup()
                            process_next_backup()
                            if options["once"]:
                                break
                            stopEvent.wait(INT_BACKUP_WORKER_REPORT_SECONDS)
                    except DatabaseError:
                        raise
                    except Exception:
                        if boolStarted:
                            try:
                                report_backup_worker(BackupWorkerStatus.FAILED)
                            except DatabaseError:
                                pass
                        raise
                    else:
                        if boolStarted:
                            report_backup_worker(BackupWorkerStatus.STOPPED)
            except (
                LocalLockUnavailableError,
                WorkerAlreadyRunningError,
                DatabaseError,
                OSError,
            ) as e:
                _LOGGER.exception("Backup worker stopped.")
                raise CommandError(
                    "Backup worker stopped: " + get_exception_summary(e)
                ) from None
        _LOGGER.info("Backup worker stopped.")
