# FileName: run_email_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from threading import Event

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError
from django.utils import timezone

from console_project.workers import stop_on_signals

from notifications.worker import (
    EmailWorkerAlreadyRunningError,
    hold_email_worker_session,
    process_next_email,
    recover_interrupted_email_deliveries,
)

_LOGGER = logging.getLogger("console.email_worker")
_INT_IDLE_POLL_SECONDS = 2


class Command(BaseCommand):
    help = "Process queued account emails without retrying attempted deliveries."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Recover interrupted attempts, process at most one pending request, then exit.",
        )

    def handle(self, *_args: object, **options: object) -> None:
        if settings.CONSOLE_URL is None:
            raise CommandError(
                "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before starting the email worker."
            )

        boolRunOnce = bool(options["once"])
        stopEvent = Event()
        try:
            with stop_on_signals(stopEvent), hold_email_worker_session():
                intRecoveredDeliveryCount = recover_interrupted_email_deliveries()
                _LOGGER.info(
                    f"Email worker started. Interrupted attempts marked Unknown: {intRecoveredDeliveryCount}."
                )
                while not stopEvent.is_set():
                    deliveryResult = process_next_email()
                    if deliveryResult is None:
                        if boolRunOnce:
                            _LOGGER.info("No pending email.")
                        floatWaitSeconds = _INT_IDLE_POLL_SECONDS
                    elif deliveryResult.retryAt is not None:
                        _LOGGER.info(
                            f"Email {deliveryResult.deliveryId}: pending until {deliveryResult.retryAt.isoformat()}."
                        )
                        floatWaitSeconds = max(
                            0, (deliveryResult.retryAt - timezone.now()).total_seconds()
                        )
                    else:
                        # Log only the record ID and status, never the recipient, body, or SMTP reply.
                        _LOGGER.info(
                            f"Email {deliveryResult.deliveryId}: {deliveryResult.status}."
                        )
                        floatWaitSeconds = 0

                    if boolRunOnce:
                        break
                    stopEvent.wait(floatWaitSeconds)
        except (EmailWorkerAlreadyRunningError, ImproperlyConfigured) as e:
            raise CommandError(str(e)) from None
        except DatabaseError:
            _LOGGER.exception("Email worker stopped after a database error.")
            # Stop instead of reconnecting without the session lock.
            raise CommandError(
                "The email worker stopped after a database error. Restore database access before restarting it."
            ) from None
        except Exception as e:
            # The next start will close any interrupted Sending record without resending it.
            _LOGGER.exception("Email worker stopped after an unexpected error.")
            raise CommandError(
                f"The email worker stopped after {type(e).__name__}. No SMTP attempt was retried."
            ) from None
        _LOGGER.info("Email worker stopped.")
