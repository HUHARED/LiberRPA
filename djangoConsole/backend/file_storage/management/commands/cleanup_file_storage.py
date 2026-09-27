# FileName: cleanup_file_storage.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from file_storage.services import cleanup_storage


class Command(BaseCommand):
    help = "Expire abandoned transfers and remove unreferenced files. Run at least once per minute."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *_args: object, **options: object) -> None:
        limit = cast(int, options["limit"])
        if not 1 <= limit <= 10000:
            raise CommandError("Use --limit between 1 and 10000.")
        deleted, failed = cleanup_storage(limit)
        self.stdout.write(f"Removed {deleted} stored files; {failed} cleanup failures.")
        if failed:
            raise CommandError(
                "Some files could not be removed. Their capacity is still charged."
            )
