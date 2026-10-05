# FileName: worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.utils import timezone
from django.db.models import Case, When, Value, IntegerField

from .delivery import EmailDeliveryResult, deliver_email
from .models import EmailStatus, EmailReasonCode, EmailDelivery, EmailType


def recover_interrupted_email_deliveries() -> int:
    """Close leftover attempts after acquiring the exclusive worker session.

    The old process may have submitted a message before losing its result.
    Preserve its token and reserved budget; never turn Sending back into Pending.
    """
    return EmailDelivery.objects.filter(status=EmailStatus.SENDING).update(
        status=EmailStatus.UNKNOWN,
        finished_at=timezone.now(),
        reason_code=EmailReasonCode.EMAIL_WORKER_INTERRUPTED,
    )


def process_next_email() -> EmailDeliveryResult | None:
    """Process the oldest pending request while the caller owns the worker session."""
    deliveryId = (
        EmailDelivery.objects
        .filter(
            status=EmailStatus.PENDING,
        )
        .annotate(
            mail_priority=Case(
                When(email_type=EmailType.RUN, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("mail_priority", "created_at", "id")
        .values_list("id", flat=True)
        .first()
    )
    if deliveryId is None:
        return None
    # The delivery service owns current eligibility, budgets, rate limits, and SMTP.
    return deliver_email(deliveryId)
