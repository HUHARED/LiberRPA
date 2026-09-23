# FileName: run_email_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pathlib import Path
from threading import Event
from traceback import walk_tb

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

_INT_IDLE_POLL_SECONDS = 2


def _build_worker_failure_details(error: Exception) -> str:
    """Describe code locations and missing attributes without including runtime values."""
    listDetail = [f"Exception type: {type(error).__name__}."]
    if isinstance(error, AttributeError):
        strAttributeName = error.name
        if strAttributeName is not None and strAttributeName.isidentifier():
            listDetail.append(f"Missing attribute: {strAttributeName}.")
        if error.obj is not None:
            listDetail.append(f"Object type: {type(error.obj).__name__}.")

    # NOTE: Omit exception text, source lines, arguments, and local variable values.
    # These can contain SMTP credentials, message bodies, or usable registration tokens.
    if error.__traceback__ is not None:
        listDetail.append("Call locations (outermost to innermost):")
        for tracebackFrame, intLineNumber in walk_tb(error.__traceback__):
            codeObj = tracebackFrame.f_code
            listDetail.append(
                f"  {Path(codeObj.co_filename).name}:{intLineNumber} in {codeObj.co_name}"
            )
    return "\n".join(listDetail)


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
                self.stdout.write(
                    f"Email worker started. Interrupted attempts marked Unknown: {intRecoveredDeliveryCount}."
                )
                while not stopEvent.is_set():
                    deliveryResult = process_next_email()
                    if deliveryResult is None:
                        if boolRunOnce:
                            self.stdout.write("No pending email.")
                        floatWaitSeconds = _INT_IDLE_POLL_SECONDS
                    elif deliveryResult.retryAt is not None:
                        self.stdout.write(
                            f"Email {deliveryResult.deliveryId}: pending until {deliveryResult.retryAt.isoformat()}."
                        )
                        floatWaitSeconds = max(
                            0, (deliveryResult.retryAt - timezone.now()).total_seconds()
                        )
                    else:
                        # Log only the record ID and status, never the recipient, body, or SMTP reply.
                        self.stdout.write(
                            f"Email {deliveryResult.deliveryId}: {deliveryResult.status}."
                        )
                        floatWaitSeconds = 0

                    if boolRunOnce:
                        break
                    stopEvent.wait(floatWaitSeconds)
        except (EmailWorkerAlreadyRunningError, ImproperlyConfigured) as e:
            raise CommandError(str(e)) from None
        except DatabaseError:
            # Stop instead of reconnecting without the session lock.
            raise CommandError(
                "The email worker stopped after a database error. Restore database access before restarting it."
            ) from None
        except Exception as e:
            # The next start will close any interrupted Sending record without resending it.
            self.stderr.write(_build_worker_failure_details(e))
            raise CommandError(
                f"The email worker stopped after {type(e).__name__}. No SMTP attempt was retried."
            ) from None
        self.stdout.write("Email worker stopped.")
