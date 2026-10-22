# FileName: cleanup_file_storage.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from operations.models import CleanupTask
from operations.cleanup_status import record_cleanup

from file_storage.services import cleanup_storage
from shared_files.cleanup import cleanup_uploads
from packages.cleanup import cleanup_uploads as cleanup_package_uploads


class Command(BaseCommand):
    help = "Expire abandoned transfers and remove unreferenced files. Run at least once per minute."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *_args: object, **options: object) -> None:
        intLimit = cast(int, options["limit"])
        if not 1 <= intLimit <= 10000:
            raise CommandError("Use --limit between 1 and 10000.")

        with record_cleanup(CleanupTask.FILE_STORAGE):
            cleanup_uploads(intLimit)
            cleanup_package_uploads(intLimit)
            intDeletedCount, intFailedCount = cleanup_storage(intLimit)
            self.stdout.write(
                f"Removed {intDeletedCount} stored files; {intFailedCount} cleanup failures."
            )
            if intFailedCount:
                raise CommandError(
                    "Some files could not be removed. Their capacity is still charged."
                )
