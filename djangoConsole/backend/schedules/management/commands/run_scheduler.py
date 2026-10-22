# FileName: run_scheduler.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from threading import Event

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError
from django.core.exceptions import ValidationError
from django.utils import timezone

from console_project.recovery import is_restored_service_pending_review
from console_project.workers import (
    SCHEDULE_WORKER_LOCK_ID,
    WorkerAlreadyRunningError,
    hold_worker_session,
    stop_on_signals,
)
from runs.worker_state import require_control_service
from operations.models import MaintenanceState
from schedules.worker import ScheduleScanWindow, scan_schedules

_LOGGER = logging.getLogger("console.scheduler")


class Command(BaseCommand):
    help = (
        "Trigger Console Schedules using their saved time zones and independent settings."
    )
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--once", action="store_true", help="Process one bounded scan and exit."
        )

    def handle(self, *_args: object, **options: object) -> None:
        stopEvent = Event()
        try:
            with (
                stop_on_signals(stopEvent),
                hold_worker_session(
                    lockId=SCHEDULE_WORKER_LOCK_ID, workerName="scheduler"
                ),
            ):
                scanWindow: ScheduleScanWindow | None = None
                _LOGGER.info("Schedule worker started.")
                while not stopEvent.is_set():
                    try:
                        control = require_control_service(timezone.now())
                        boolReady = (
                            (
                                control.recovery_until is None
                                or control.recovery_until <= timezone.now()
                            )
                            and not is_restored_service_pending_review()
                            and not MaintenanceState.objects.filter(
                                pk=1, entered_at__isnull=False
                            ).exists()
                        )
                    except ValidationError:
                        boolReady = False
                    if not boolReady:
                        scanWindow = None
                        if options["once"]:
                            _LOGGER.info(
                                "Schedule triggers are paused for maintenance or run control recovery."
                            )
                            break
                        stopEvent.wait(0.5)
                        continue
                    scanWindow = scan_schedules(scanWindow)
                    if options["once"]:
                        break
                    stopEvent.wait(0.01 if scanWindow is not None else 0.5)
        except (WorkerAlreadyRunningError, DatabaseError) as e:
            raise CommandError("Schedule worker stopped: " + type(e).__name__) from None
        _LOGGER.info("Schedule worker stopped.")
