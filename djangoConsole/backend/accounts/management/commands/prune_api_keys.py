# FileName: prune_api_keys.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from accounts.api_keys import prune_inactive_api_keys


class Command(BaseCommand):
    help = "Delete inactive API key metadata beyond the configured age and count limits."
    requires_migrations_checks = True

    def handle(self, *_args: object, **_options: object) -> None:
        try:
            intDeletedCount = prune_inactive_api_keys()
        except DatabaseError:
            raise CommandError(
                "API key cleanup stopped after a database error; it can be rerun."
            ) from None
        self.stdout.write(f"Deleted {intDeletedCount} inactive API key record(s).")
