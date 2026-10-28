# FileName: maintenance.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from typing import cast

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from console_project.logging import get_exception_summary
from console_project.formatters import format_instance_time
from operations.contracts import MaintenanceAction
from operations.maintenance import load_maintenance_status, update_maintenance

_LOGGER = logging.getLogger("console.operations")


class Command(BaseCommand):
    help = "Show maintenance status, pause new work, or resume service after checks."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "action",
            nargs="?",
            default="status",
            choices=("status", *MaintenanceAction.values),
            help="status (default), enter, or resume; existing Runs are not stopped.",
        )

    def handle(self, *_args: object, **options: object) -> None:
        strAction = cast(str, options["action"])
        try:
            if strAction == "status":
                status = load_maintenance_status()
                self.stdout.write(f"Service state: {status.state.label}")
                self.stdout.write(f"Entered at: {format_instance_time(status.enteredAt)}")
                self.stdout.write(f"Active jobs: {status.activeJobs}")
                self.stdout.write(f"Running runs: {status.runningRuns}")
                self.stdout.write(f"Jobs needing review: {status.jobsNeedingReview}")
                self.stdout.write(f"Can resume: {'yes' if status.canResume else 'no'}")
                if status.resumeBlockReason:
                    self.stdout.write(f"Resume blocked: {status.resumeBlockReason}")
                self.stdout.write(f"Checked at: {format_instance_time(status.updatedAt)}")
                return
            action = MaintenanceAction(strAction)
            boolChanged = update_maintenance(action)
            if action == MaintenanceAction.ENTER:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Maintenance entered."
                        if boolChanged
                        else "Already in maintenance."
                    )
                )
                self.stdout.write(
                    "New jobs, schedule triggers and start permissions are paused. "
                    "Existing Runs and valid reports can continue."
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Service resumed."
                        if boolChanged
                        else "Service is already normal."
                    )
                )
        except ValidationError as e:
            raise CommandError(" ".join(e.messages)) from None
        except (ImproperlyConfigured, DatabaseError, OSError) as e:
            _LOGGER.exception("Maintenance command failed: action=%s.", strAction)
            raise CommandError(
                "Maintenance command failed: " + get_exception_summary(e)
            ) from None
