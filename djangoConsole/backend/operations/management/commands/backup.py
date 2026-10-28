# FileName: backup.py
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
from console_project.formatters import format_instance_time, format_file_size
from operations.backup_contracts import BackupStatus, BackupRecordInfo
from operations.backup_jobs import request_backup, load_backup_status

_LOGGER = logging.getLogger("console.backup")


class Command(BaseCommand):
    help = "Request an online backup or show the worker, progress and retained results."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "action",
            nargs="?",
            default="status",
            choices=("status", "request"),
            help="status (default) or request; the backup worker performs accepted work.",
        )

    def handle(self, *_args: object, **options: object) -> None:
        def _write_record(label: str, record: BackupRecordInfo | None) -> None:
            self.stdout.write("")
            self.stdout.write(f"{label}: {record.id if record else '-'}")
            if record is None:
                return
            self.stdout.write(f"  Status: {record.status.label}")
            self.stdout.write(f"  Source: {record.source.label}")
            self.stdout.write(f"  Stage: {record.stage.label if record.stage else '-'}")
            self.stdout.write(f"  Requested at: {format_instance_time(record.createdAt)}")
            self.stdout.write(f"  Started at: {format_instance_time(record.startedAt)}")
            self.stdout.write(f"  Data as of: {format_instance_time(record.dataAsOf)}")
            self.stdout.write(f"  Ended at: {format_instance_time(record.endedAt)}")
            self.stdout.write(
                f"  Size: {format_file_size(record.sizeBytes) if record.sizeBytes is not None else '-'}"
            )
            if record.details:
                self.stdout.write(f"  Details: {record.details}")
            if record.cleanupError:
                self.stdout.write(f"  Cleanup warning: {record.cleanupError}")

        strAction = cast(str, options["action"])
        try:
            if strAction == "request":
                record, boolCreated = request_backup()
                strMessage = (
                    "Backup request accepted" if boolCreated else "Backup already active"
                )
                self.stdout.write(
                    f"{strMessage}: {record.id} ({BackupStatus(record.status).label})."
                )
                self.stdout.write(
                    "The worker runs independently. Use 'backup status' to check the result."
                )
                return
            status = load_backup_status()
            self.stdout.write(
                f"Backups configured: {'yes' if status.configured else 'no'}"
            )
            self.stdout.write(f"Location: {status.location or '-'}")
            self.stdout.write(
                f"Daily time: {status.dailyTime + ' ' + status.timeZone if status.dailyTime else '-'}"
            )
            self.stdout.write(f"Backup retention limit: {status.retentionCount}")
            self.stdout.write(f"Worker health: {status.healthStatus.label}")
            self.stdout.write(
                f"Worker checked at: {format_instance_time(status.checkedAt)}"
            )
            self.stdout.write(f"Health message: {status.healthMessage}")
            self.stdout.write(f"Can request: {'yes' if status.canStart else 'no'}")
            if status.blockedReason:
                self.stdout.write(f"Request blocked: {status.blockedReason}")
            self.stdout.write(f"Checked at: {format_instance_time(status.updatedAt)}")
            _write_record("Current backup", status.current)
            _write_record("Latest result", status.latestResult)
            if (
                status.lastSuccess is not None
                and status.latestResult is not None
                and status.lastSuccess.id == status.latestResult.id
            ):
                self.stdout.write("\nLast successful backup: same as latest result.")
            else:
                _write_record("Last successful backup", status.lastSuccess)
        except ValidationError as e:
            raise CommandError(" ".join(e.messages)) from None
        except (ImproperlyConfigured, DatabaseError, OSError) as e:
            _LOGGER.exception("Backup command failed: action=%s.", strAction)
            raise CommandError(
                "Backup command failed: " + get_exception_summary(e)
            ) from None
