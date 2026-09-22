# FileName: deletion_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from collections.abc import Generator
from contextlib import contextmanager

from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from .cleanup import (
    OrganizationDeletionResult,
    complete_organization_deletion,
    start_next_organization_deletion,
)

# Share the "LRPA" namespace with the email worker, using a separate session lock.
_INT_LOCK_NAMESPACE = int.from_bytes(b"LRPA", "big")
_INT_DELETION_WORKER_LOCK = 2


class OrganizationDeletionWorkerAlreadyRunningError(Exception):
    """Another process owns this database's organization deletion worker session."""


@contextmanager
def hold_organization_deletion_worker_session() -> Generator[None]:
    """Keep cleanup exclusive across commits and stop rather than reconnect after database errors."""
    if connection.vendor != "postgresql":
        raise ImproperlyConfigured(
            "The organization deletion worker requires PostgreSQL."
        )
    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError(
            "The organization deletion worker must run outside a database transaction."
        )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s, %s)",
                [_INT_LOCK_NAMESPACE, _INT_DELETION_WORKER_LOCK],
            )
            lockAcquired = cursor.fetchone()[0]
        if not lockAcquired:
            raise OrganizationDeletionWorkerAlreadyRunningError(
                "Another organization deletion worker is already running for this database."
            )
        yield
    finally:
        connection.close()


def process_next_organization_deletion() -> OrganizationDeletionResult | None:
    """Process or resume one due deletion while the caller owns the worker session."""
    organizationId = start_next_organization_deletion()
    if organizationId is None:
        return None
    return complete_organization_deletion(organizationId)
