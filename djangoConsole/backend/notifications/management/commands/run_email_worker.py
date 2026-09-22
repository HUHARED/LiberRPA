# FileName: run_email_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import signal
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from traceback import walk_tb
from types import FrameType

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError
from django.utils import timezone

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
        attributeName = error.name
        if attributeName is not None and attributeName.isidentifier():
            listDetail.append(f"Missing attribute: {attributeName}.")
        if error.obj is not None:
            listDetail.append(f"Object type: {type(error.obj).__name__}.")

    # NOTE: Omit exception text, source lines, arguments, and local variable values.
    # These can contain SMTP credentials, message bodies, or usable registration tokens.
    if error.__traceback__ is not None:
        listDetail.append("Call locations (outermost to innermost):")
        for tracebackFrame, lineNumber in walk_tb(error.__traceback__):
            code = tracebackFrame.f_code
            listDetail.append(
                f"  {Path(code.co_filename).name}:{lineNumber} in {code.co_name}"
            )
    return "\n".join(listDetail)


@contextmanager
def _stop_on_signals(stopEvent: Event) -> Generator[None]:
    """Finish an active SMTP attempt before stopping; wake an idle worker immediately."""

    def request_stop(_signalNumber: int, _frame: FrameType | None) -> None:
        stopEvent.set()

    stopSignals = (signal.SIGINT, signal.SIGTERM)
    dictPreviousSignalHandler = {
        signalNumber: signal.getsignal(signalNumber) for signalNumber in stopSignals
    }
    try:
        for signalNumber in stopSignals:
            signal.signal(signalNumber, request_stop)
        yield
    finally:
        for signalNumber, previousHandler in dictPreviousSignalHandler.items():
            if previousHandler is not None:
                signal.signal(signalNumber, previousHandler)


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

        runOnce = bool(options["once"])
        stopEvent = Event()
        try:
            with _stop_on_signals(stopEvent), hold_email_worker_session():
                recoveredDeliveryCount = recover_interrupted_email_deliveries()
                self.stdout.write(
                    f"Email worker started. Interrupted attempts marked Unknown: {recoveredDeliveryCount}."
                )
                while not stopEvent.is_set():
                    deliveryResult = process_next_email()
                    if deliveryResult is None:
                        if runOnce:
                            self.stdout.write("No pending email.")
                        waitSeconds = _INT_IDLE_POLL_SECONDS
                    elif deliveryResult.retryAt is not None:
                        self.stdout.write(
                            f"Email {deliveryResult.deliveryId}: pending until {deliveryResult.retryAt.isoformat()}."
                        )
                        waitSeconds = max(
                            0, (deliveryResult.retryAt - timezone.now()).total_seconds()
                        )
                    else:
                        # Log only the record ID and status, never the recipient, body, or SMTP reply.
                        self.stdout.write(
                            f"Email {deliveryResult.deliveryId}: {deliveryResult.status}."
                        )
                        waitSeconds = 0

                    if runOnce:
                        break
                    stopEvent.wait(waitSeconds)
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
