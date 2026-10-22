# FileName: instance_status.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from datetime import datetime, UTC

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from console_project.logging import get_exception_summary
from operations.instance_status import load_instance_summary

_LOGGER = logging.getLogger("console.operations")


class Command(BaseCommand):
    help = "Show component health, file storage space and the last successful backup."
    # Report database failures without a migration precheck hiding the other results.
    requires_migrations_checks = False

    def handle(self, *_args: object, **_options: object) -> None:
        def _format_time(value: datetime | None) -> str:
            return value.astimezone(UTC).isoformat(timespec="seconds") if value else "-"

        try:
            summary = load_instance_summary()
            self.stdout.write(f"Console version: {summary.version}")
            self.stdout.write(
                f"Service state: {summary.serviceState.label if summary.serviceState else 'Unknown'}"
            )
            self.stdout.write(
                f"Maintenance entered at: {_format_time(summary.maintenanceEnteredAt)}"
            )
            self.stdout.write(f"Instance time zone: {summary.timeZone}")
            self.stdout.write(f"Checked at: {_format_time(summary.updatedAt)}")

            for component in summary.components:
                self.stdout.write(
                    f"\n{component.component.label}: {component.status.label}"
                )
                self.stdout.write(f"  Checked at: {_format_time(component.checkedAt)}")
                self.stdout.write(f"  Message: {component.message}")

            storage = summary.storage
            self.stdout.write(f"\nFile storage volume: {storage.status.label}")
            self.stdout.write(f"  Checked at: {_format_time(storage.checkedAt)}")
            self.stdout.write(f"  Message: {storage.message}")
            self.stdout.write(
                f"  Total (bytes): {storage.totalBytes if storage.totalBytes is not None else '-'}"
            )
            self.stdout.write(
                f"  Used (bytes): {storage.usedBytes if storage.usedBytes is not None else '-'}"
            )
            self.stdout.write(
                f"  Free (bytes): {storage.freeBytes if storage.freeBytes is not None else '-'}"
            )

            backup = summary.lastSuccessfulBackup
            self.stdout.write("\nLast successful backup:")
            if backup is None:
                self.stdout.write("  No successful backup information is available.")
            else:
                self.stdout.write(f"  ID: {backup.id}")
                self.stdout.write(f"  Data as of: {_format_time(backup.dataAsOf)}")
                self.stdout.write(f"  Ended at: {_format_time(backup.endedAt)}")
                self.stdout.write(f"  Size (bytes): {backup.sizeBytes}")
        except (ImproperlyConfigured, DatabaseError, OSError) as e:
            _LOGGER.exception("Instance status command failed.")
            raise CommandError(
                "Instance status could not be read: " + get_exception_summary(e)
            ) from None
