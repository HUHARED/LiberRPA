# FileName: workers.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import signal
from collections.abc import Generator
from contextlib import contextmanager
from threading import Event
from types import FrameType

from django.core.exceptions import ImproperlyConfigured
from django.db import connection

_INT_LOCK_NAMESPACE = int.from_bytes(b"LRPA", "big")
# NOTE: Keep worker lock IDs distinct so different worker kinds can run together.
EMAIL_WORKER_LOCK_ID = 1
ORGANIZATION_DELETION_WORKER_LOCK_ID = 2
SCHEDULE_WORKER_LOCK_ID = 3
RUN_WORKER_LOCK_ID = 4
BACKUP_WORKER_LOCK_ID = 5
CAPACITY_CHECK_LOCK_ID = 6


class WorkerAlreadyRunningError(Exception):
    """Another database session already owns this worker's lock."""


@contextmanager
def hold_worker_session(*, lockId: int, workerName: str) -> Generator[None]:
    """Hold one standalone worker's database session across its per-item transactions."""
    if connection.vendor != "postgresql":
        raise ImproperlyConfigured(f"The {workerName} worker requires PostgreSQL.")
    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError(
            f"The {workerName} worker must run outside a database transaction."
        )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT PG_TRY_ADVISORY_LOCK(%s, %s)",
                [_INT_LOCK_NAMESPACE, lockId],
            )
            boolLockAcquired = cursor.fetchone()[0]
        if not boolLockAcquired:
            raise WorkerAlreadyRunningError(
                f"Another {workerName} worker is already running for this database."
            )
        # NOTE: Do not recycle this connection or reconnect after an error; the session owns the lock.
        yield
    finally:
        # Closing the session releases its lock after normal completion or an error.
        connection.close()


@contextmanager
def stop_on_signals(stopEvent: Event) -> Generator[None]:
    """Finish the current work item before stopping and wake an idle worker immediately."""

    def request_stop(_signalNumber: int, _frame: FrameType | None) -> None:
        stopEvent.set()

    tupleSignal = (signal.SIGINT, signal.SIGTERM)
    dictPreviousSignalHandler = {
        signalNumber: signal.getsignal(signalNumber) for signalNumber in tupleSignal
    }
    try:
        for signalNumber in tupleSignal:
            signal.signal(signalNumber, request_stop)
        yield
    finally:
        for signalNumber, previousHandler in dictPreviousSignalHandler.items():
            if previousHandler is not None:
                signal.signal(signalNumber, previousHandler)
