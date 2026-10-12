# FileName: cleanup_run_data.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from runs.retention import cleanup_run_data


class Command(BaseCommand):
    help = "Remove expired Run History and central logs without changing active work."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *_args: object, **options: object) -> None:
        intLimit = cast(int, options["limit"])
        if not 1 <= intLimit <= 10000:
            raise CommandError("Use --limit between 1 and 10000.")
        intJobs, intLogs = cleanup_run_data(intLimit)
        self.stdout.write(
            f"Removed {intJobs} finished Jobs and cleared {intLogs} log groups."
        )
