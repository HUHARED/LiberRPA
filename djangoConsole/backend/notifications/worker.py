# FileName: worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from collections.abc import Generator
from contextlib import contextmanager

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.utils import timezone

from .delivery import EmailDeliveryResult, deliver_email
from .models import EmailDelivery, EmailStatus

# Two PostgreSQL advisory-lock keys: the "LRPA" namespace and its email worker.
_INT_LOCK_NAMESPACE = int.from_bytes(b"LRPA", "big")
_INT_EMAIL_WORKER_LOCK = 1


class EmailWorkerAlreadyRunningError(Exception):
    """Another process owns this database's email worker session."""


@contextmanager
def hold_email_worker_session() -> Generator[None]:
    """Keep the standalone worker's database session exclusive until it exits.

    This session lock survives commits without holding a database transaction open.
    Do not recycle the command's connection or reconnect after a database error.
    All queue delivery and recovery must run inside this session.
    """
    if connection.vendor != "postgresql":
        raise ImproperlyConfigured("The email worker requires PostgreSQL.")
    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError("The email worker must run outside a database transaction.")

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s, %s)",
                [_INT_LOCK_NAMESPACE, _INT_EMAIL_WORKER_LOCK],
            )
            lockAcquired = cursor.fetchone()[0]
        if not lockAcquired:
            raise EmailWorkerAlreadyRunningError(
                "Another email worker is already running for this database."
            )
        yield
    finally:
        # Closing the session releases its advisory lock, including after an error.
        connection.close()


def recover_interrupted_email_deliveries() -> int:
    """Close leftover attempts after acquiring the exclusive worker session.

    The old process may have submitted a message before losing its result.
    Preserve its token and reserved budget; never turn Sending back into Pending.
    """
    return EmailDelivery.objects.filter(status=EmailStatus.SENDING).update(
        status=EmailStatus.UNKNOWN,
        finished_at=timezone.now(),
        reason_code="email_worker_interrupted",
    )


def process_next_email() -> EmailDeliveryResult | None:
    """Process the oldest pending request while the caller owns the worker session."""
    deliveryId = (
        EmailDelivery.objects
        .filter(
            status=EmailStatus.PENDING,
        )
        .order_by("created_at", "id")
        .values_list("id", flat=True)
        .first()
    )
    if deliveryId is None:
        return None
    # The delivery service owns current eligibility, budgets, rate limits, and SMTP.
    return deliver_email(deliveryId)
