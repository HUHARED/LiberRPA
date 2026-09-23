# FileName: run_organization_deletion_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from threading import Event

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from console_project.workers import stop_on_signals

from organizations.deletion_worker import (
    OrganizationDeletionWorkerAlreadyRunningError,
    hold_organization_deletion_worker_session,
    process_next_organization_deletion,
)

_INT_IDLE_POLL_SECONDS = 2


class Command(BaseCommand):
    help = (
        "Delete due organizations and queue completion notices for their former members."
    )
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one due or interrupted organization deletion, then exit.",
        )

    def handle(self, *_args: object, **options: object) -> None:
        boolRunOnce = bool(options["once"])
        stopEvent = Event()
        try:
            with stop_on_signals(stopEvent), hold_organization_deletion_worker_session():
                self.stdout.write("Organization deletion worker started.")
                while not stopEvent.is_set():
                    deletionResult = process_next_organization_deletion()
                    if deletionResult is None:
                        if boolRunOnce:
                            self.stdout.write("No due organization deletion.")
                        intWaitSeconds = _INT_IDLE_POLL_SECONDS
                    else:
                        # Log identifiers and counts only, never member addresses or organization notes.
                        self.stdout.write(
                            f"Organization {deletionResult.organizationId}: deleted; "
                            f"accounts: {deletionResult.deletedAccountCount}; "
                            f"completion emails queued: {deletionResult.queuedEmailCount}."
                        )
                        intWaitSeconds = 0
                    if boolRunOnce:
                        break
                    stopEvent.wait(intWaitSeconds)
        except (OrganizationDeletionWorkerAlreadyRunningError, ImproperlyConfigured) as e:
            raise CommandError(str(e)) from None
        except DatabaseError:
            raise CommandError(
                "The organization deletion worker stopped after a database error. "
                "Restore database access before restarting; started deletions remain frozen and can be resumed."
            ) from None
        except Exception as e:
            raise CommandError(
                f"The organization deletion worker stopped after {type(e).__name__}. "
                "Resolve the failure before restarting; started deletions remain frozen and can be resumed."
            ) from None
        self.stdout.write("Organization deletion worker stopped.")
