# FileName: check_capacity.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from console_project.logging import get_exception_summary
from console_project.recovery import is_restored_service_pending_review
from console_project.workers import WorkerAlreadyRunningError
from operations.capacity import check_capacity

_LOGGER = logging.getLogger("console.capacity")


class Command(BaseCommand):
    help = "Check storage and organization capacities once, record usage and queue due notices."
    requires_migrations_checks = True

    def handle(self, *_args: object, **_options: object) -> None:
        try:
            if is_restored_service_pending_review():
                _LOGGER.debug(
                    "Capacity notices are paused until the restored instance is reviewed."
                )
                return
            result = check_capacity()
            _LOGGER.log(
                logging.INFO if result.queuedEmailCount else logging.DEBUG,
                "Capacity check completed: organizations=%s, queued_emails=%s.",
                result.organizationCount,
                result.queuedEmailCount,
            )
            if not result.storageAvailable:
                _LOGGER.warning(
                    "Storage capacity is unknown. Check the configured storage directory and runtime log."
                )
        except WorkerAlreadyRunningError as e:
            raise CommandError(str(e)) from None
        except (ImproperlyConfigured, OSError) as e:
            _LOGGER.exception("Capacity check failed.")
            raise CommandError(
                "Capacity check failed: " + get_exception_summary(e)
            ) from None
