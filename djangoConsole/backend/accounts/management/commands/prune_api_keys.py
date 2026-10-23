# FileName: prune_api_keys.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.management.base import BaseCommand

from operations.models import CleanupTask
from operations.cleanup_status import record_cleanup

from accounts.api_keys import prune_inactive_api_keys


class Command(BaseCommand):
    help = (
        "Delete inactive API key metadata beyond the configured age and count limits. "
        "Run at least once per hour."
    )
    requires_migrations_checks = True

    def handle(self, *_args: object, **_options: object) -> None:
        with record_cleanup(CleanupTask.API_KEYS):
            intDeletedCount = prune_inactive_api_keys()
        self.stdout.write(f"Deleted {intDeletedCount} inactive API key record(s).")
