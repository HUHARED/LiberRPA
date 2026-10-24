# FileName: check_capacity.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from contextlib import nullcontext
from threading import Event
from time import monotonic

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser

from console_project.logging import get_exception_summary
from console_project.recovery import is_restored_service_pending_review
from console_project.workers import WorkerAlreadyRunningError, stop_on_signals
from operations.capacity_contracts import INT_CAPACITY_CHECK_SECONDS
from operations.capacity import check_capacity

_LOGGER = logging.getLogger("console.capacity")


class Command(BaseCommand):
    help = "Check storage and organization capacities, record current usage and queue due notices."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--watch",
            action="store_true",
            help="Repeat hourly by default; deployment uses the history-cleanup loop.",
        )
        parser.add_argument(
            "--interval-minutes",
            type=int,
            help="Minutes between checks with --watch (default: 60).",
        )

    def handle(self, *_args: object, **options: object) -> None:
        boolWatch = options["watch"] is True
        intIntervalMinutes = options["interval_minutes"]
        if intIntervalMinutes is not None:
            if not boolWatch:
                raise CommandError("--interval-minutes requires --watch.")
            if not isinstance(intIntervalMinutes, int) or intIntervalMinutes < 1:
                raise CommandError("--interval-minutes must be at least 1.")
        intIntervalSeconds = (
            INT_CAPACITY_CHECK_SECONDS
            if intIntervalMinutes is None
            else intIntervalMinutes * 60
        )
        stopEvent = Event()
        try:
            with stop_on_signals(stopEvent) if boolWatch else nullcontext():
                while not stopEvent.is_set():
                    if is_restored_service_pending_review():
                        self.stdout.write(
                            "Capacity notices are paused until the restored instance is reviewed."
                        )
                    else:
                        result = check_capacity()
                        self.stdout.write(
                            f"Capacity check completed: organizations={result.organizationCount}, queued emails={result.queuedEmailCount}."
                        )
                        if not result.storageAvailable:
                            self.stderr.write(
                                "Storage capacity is unknown. Check the configured storage directory and runtime log."
                            )
                    if not boolWatch:
                        break
                    floatNextCheck = monotonic() + intIntervalSeconds
                    while not stopEvent.is_set():
                        floatRemainingSeconds = floatNextCheck - monotonic()
                        if floatRemainingSeconds <= 0:
                            break
                        # Short waits let Windows Python 3.13 process Ctrl+C without waiting for the full interval.
                        stopEvent.wait(min(floatRemainingSeconds, 0.5))
        except WorkerAlreadyRunningError as e:
            raise CommandError(str(e)) from None
        except (ImproperlyConfigured, OSError) as e:
            _LOGGER.exception("Capacity check failed.")
            raise CommandError(
                "Capacity check failed: " + get_exception_summary(e)
            ) from None
