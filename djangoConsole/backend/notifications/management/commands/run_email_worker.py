# FileName: run_email_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from threading import Event
from time import monotonic

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError
from django.utils import timezone

from console_project.workers import (
    EMAIL_WORKER_LOCK_ID,
    WorkerAlreadyRunningError,
    hold_worker_session,
    stop_on_signals,
)

from notifications.models import EmailWorkerStatus, EmailWorkerState
from notifications.worker import (
    INT_EMAIL_WORKER_REPORT_SECONDS,
    recover_interrupted_email_deliveries,
    process_next_email,
)

_LOGGER = logging.getLogger("console.email_worker")
_INT_IDLE_POLL_SECONDS = 2


class Command(BaseCommand):
    help = "Process queued Console emails without retrying attempted deliveries."
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Recover interrupted attempts, process at most one pending request, then exit.",
        )

    def handle(self, *_args: object, **options: object) -> None:
        boolRunOnce = bool(options["once"])
        stopEvent = Event()
        reportedStatus: EmailWorkerStatus | None = None
        floatReportedAt = 0.0

        def report_status(status: EmailWorkerStatus) -> None:
            nonlocal reportedStatus, floatReportedAt
            floatCurrentTime = monotonic()
            if (
                status == reportedStatus
                and floatCurrentTime - floatReportedAt < INT_EMAIL_WORKER_REPORT_SECONDS
            ):
                return
            # The caller still owns the exclusive database session; never write after releasing it.
            EmailWorkerState.objects.update_or_create(
                pk=1, defaults={"status": status, "checked_at": timezone.now()}
            )
            reportedStatus = status
            floatReportedAt = floatCurrentTime

        try:
            with (
                stop_on_signals(stopEvent),
                hold_worker_session(lockId=EMAIL_WORKER_LOCK_ID, workerName="email"),
            ):
                try:
                    report_status(EmailWorkerStatus.STARTING)
                    intRecoveredDeliveryCount = recover_interrupted_email_deliveries()
                    _LOGGER.info(
                        f"Email worker started. Interrupted attempts marked Unknown: {intRecoveredDeliveryCount}."
                    )
                    while not stopEvent.is_set():
                        deliveryResult = process_next_email()
                        report_status(EmailWorkerStatus.RUNNING)
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
                        floatWaitUntil = monotonic() + floatWaitSeconds
                        while not stopEvent.is_set():
                            floatCurrentTime = monotonic()
                            floatRemainingSeconds = floatWaitUntil - floatCurrentTime
                            if floatRemainingSeconds <= 0:
                                break
                            floatReportAfter = max(
                                0,
                                floatReportedAt
                                + INT_EMAIL_WORKER_REPORT_SECONDS
                                - floatCurrentTime,
                            )
                            if stopEvent.wait(min(floatRemainingSeconds, floatReportAfter)):
                                break
                            # Long allowance waits refresh activity without processing or sending early.
                            report_status(EmailWorkerStatus.RUNNING)
                    report_status(EmailWorkerStatus.STOPPED)
                except DatabaseError:
                    # A failed session cannot safely record another status or reconnect without its lock.
                    raise
                except Exception:
                    try:
                        report_status(EmailWorkerStatus.FAILED)
                    except DatabaseError as e:
                        _LOGGER.warning(
                            "Could not record email worker failure: %s", type(e).__name__
                        )
                    raise
        except (WorkerAlreadyRunningError, ImproperlyConfigured) as e:
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
