# FileName: run_activity.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from console_project.logging import get_exception_summary
from operations.run_activity import load_run_activity

_LOGGER = logging.getLogger("console.operations")


class Command(BaseCommand):
    help = "Show average concurrent Runs by UTC hour over the last 14 complete UTC days."
    requires_migrations_checks = True

    def handle(self, *_args: object, **_options: object) -> None:
        try:
            summary = load_run_activity()
        except (ImproperlyConfigured, DatabaseError) as e:
            _LOGGER.exception("Run activity query failed.")
            raise CommandError(
                "Run activity query failed: " + get_exception_summary(e)
            ) from None

        self.stdout.write(
            f"Window: {summary.windowStart.isoformat(timespec='seconds')} to {summary.windowEnd.isoformat(timespec='seconds')} (end excluded)"
        )
        self.stdout.write(
            "Based on retained Runs with known end times; each hour averages 14 days."
        )
        self.stdout.write(f"{'Hour (UTC)':<16} {'Average concurrent Runs':>24}")
        for intHour, average in enumerate(summary.averageConcurrentRuns):
            strHour = f"{intHour:02d}:00-{intHour + 1:02d}:00"
            self.stdout.write(f"{strHour:<16} {average:>24.6f}")
        self.stdout.write(
            f"Excluded retained Runs with unknown end times, started before the window end: {summary.incompleteRunCount}. "
            "These may predate the window."
        )
        self.stdout.write(
            f"Checked at: {summary.updatedAt.isoformat(timespec='seconds')}"
        )
