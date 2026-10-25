# FileName: prune_email_deliveries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.core.management.base import BaseCommand, CommandError, CommandParser

from operations.models import CleanupTask
from operations.cleanup_status import record_cleanup

from notifications.email_retention import prune_email_deliveries

_LOGGER = logging.getLogger("console.email_retention")


class Command(BaseCommand):
    help = (
        "Prune expired and excess completed email deliveries. Run at least once per hour."
    )
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *_args: object, **options: object) -> None:
        try:
            intBatchSize = int(str(options["batch_size"]))
            if not 1 <= intBatchSize <= 10000:
                raise ValueError("Batch size must be between 1 and 10000.")

            with record_cleanup(CleanupTask.EMAIL_HISTORY):
                intDeletedCount = prune_email_deliveries(batchSize=intBatchSize)
        except ValueError as e:
            raise CommandError(str(e)) from None
        _LOGGER.log(
            logging.INFO if intDeletedCount else logging.DEBUG,
            "Email history cleanup completed: deleted=%s.",
            intDeletedCount,
        )
