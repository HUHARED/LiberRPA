# FileName: prune_audit_records.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from operations.audit_retention import prune_audit_records

_LOGGER = logging.getLogger("console.audit")


class Command(BaseCommand):
    help = "Prune expired and excess organization/platform audit records."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *_args: object, **options: object) -> None:
        try:
            intDeletedCount = prune_audit_records(
                batchSize=int(str(options["batch_size"]))
            )
        except ValueError as e:
            raise CommandError(str(e)) from None
        except DatabaseError:
            _LOGGER.exception("Audit retention cleanup stopped after a database error.")
            raise CommandError(
                "Audit cleanup failed. Check the runtime log before retrying."
            ) from None
        _LOGGER.info("Audit retention cleanup completed: deleted=%s.", intDeletedCount)
