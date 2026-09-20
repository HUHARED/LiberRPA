# FileName: delivery.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from accounts.emails import build_registration_email
from accounts.registration import issue_registration_token
from console_project.config import LimitsConfig

from .models import EmailDelivery, EmailDispatchState, EmailStatus, EmailType
from .smtp import send_smtp_once

_BUDGET_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class EmailPreparationResult:
    """Private worker result; a prepared message must never be returned through a public API."""

    delivery_id: uuid.UUID
    status: EmailStatus
    message: EmailMessage | None = field(default=None, repr=False)
    retry_at: datetime | None = None


@dataclass(frozen=True)
class EmailDeliveryResult:
    """Worker progress without the prepared message or its registration token."""

    delivery_id: uuid.UUID
    status: EmailStatus
    retry_at: datetime | None = None


def _refill_allowance(
    dispatchState: EmailDispatchState, *, currentTime: datetime, limits: LimitsConfig
) -> None:
    """Update the already locked rate state in memory, preserving partial refill intervals."""
    interval = timedelta(seconds=limits.emailRefillSeconds)
    elapsedUnits = max(0, (currentTime - dispatchState.refilled_at) // interval)
    dispatchState.available_units = min(
        limits.emailBurstRecipients, dispatchState.available_units + elapsedUnits
    )
    if dispatchState.available_units == limits.emailBurstRecipients:
        # Time spent with a full allowance cannot accumulate an extra burst.
        dispatchState.refilled_at = currentTime
    else:
        dispatchState.refilled_at += elapsedUnits * interval


def _mark_not_sent(delivery: EmailDelivery, *, reasonCode: str) -> EmailPreparationResult:
    """Finish a locked pending request without reserving a recipient unit."""
    delivery.status = EmailStatus.NOT_SENT
    delivery.finished_at = timezone.now()
    delivery.reason_code = reasonCode
    delivery.save(update_fields=["status", "finished_at", "reason_code"])
    return EmailPreparationResult(delivery_id=delivery.id, status=EmailStatus.NOT_SENT)


@sensitive_variables()
@transaction.atomic(durable=True)
def prepare_registration_email(deliveryId: uuid.UUID) -> EmailPreparationResult:
    """Commit one registration email reservation and its token before an SMTP attempt.

    Call this from the delivery worker outside any surrounding transaction.
    A message grants one immediate attempt; retry_at schedules only an unattempted request.
    This function does not contact SMTP or recover an earlier Sending request.
    """
    if settings.CONSOLE_URL is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before preparing email."
        )

    delivery = EmailDelivery.objects.select_for_update().get(pk=deliveryId)
    if delivery.email_type != EmailType.ORGANIZATION_REGISTRATION:
        raise ValueError("This request is not a registration email.")
    if delivery.status != EmailStatus.PENDING:
        return EmailPreparationResult(
            delivery_id=delivery.id, status=EmailStatus(delivery.status)
        )

    # All mail types must take this shared lock before reserving SMTP capacity.
    # Lock order is delivery, dispatch state, registration token, then instance policy.
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    dispatchState, _ = EmailDispatchState.objects.select_for_update().get_or_create(
        pk=1,
        defaults={"available_units": limits.emailBurstRecipients},
    )
    currentTime = timezone.now()
    usedUnits = EmailDelivery.objects.filter(
        attempted_at__gt=currentTime - _BUDGET_WINDOW
    ).count()
    if usedUnits >= limits.maxEmailRecipientsPer24Hours:
        return _mark_not_sent(delivery, reasonCode="smtp_budget_exhausted")

    _refill_allowance(dispatchState, currentTime=currentTime, limits=limits)
    if dispatchState.available_units == 0:
        retryAt = dispatchState.refilled_at + timedelta(seconds=limits.emailRefillSeconds)
        return EmailPreparationResult(
            delivery_id=delivery.id,
            status=EmailStatus.PENDING,
            retry_at=retryAt,
        )

    # Issuance rechecks the current account, resend interval, and creation policy.
    # Its savepoint rolls back token changes if the policy rejects registration.
    try:
        tokenDelivery = issue_registration_token(delivery.recipient)
    except PermissionDenied:
        return _mark_not_sent(delivery, reasonCode="organization_creation_disabled")
    if tokenDelivery is None:
        return _mark_not_sent(delivery, reasonCode="registration_not_eligible")

    message = build_registration_email(tokenDelivery)
    attemptedAt = timezone.now()
    # The dispatch lock prevents other reservations while token or policy locks are awaited.
    # Budget usage cannot grow here; refresh only the rate allowance and attempt timestamp.
    _refill_allowance(dispatchState, currentTime=attemptedAt, limits=limits)
    dispatchState.available_units -= 1
    dispatchState.save(update_fields=["available_units", "refilled_at"])

    delivery.status = EmailStatus.SENDING
    delivery.attempted_at = attemptedAt
    delivery.save(update_fields=["status", "attempted_at"])
    # The token digest, budget reservation, and Sending state commit together.
    # Never release the reservation after an SMTP failure or an uncertain outcome.
    return EmailPreparationResult(
        delivery_id=delivery.id, status=EmailStatus.SENDING, message=message
    )


@sensitive_variables()
def deliver_registration_email(deliveryId: uuid.UUID) -> EmailDeliveryResult:
    """Prepare, attempt SMTP once, and record the outcome without holding network-time locks.

    Call outside any surrounding transaction; preparation enforces its own commit boundary.
    A repeated call for a Sending or finished record does not send the message again.
    If result persistence fails, leave Sending for worker recovery; never repeat SMTP.
    """
    preparation = prepare_registration_email(deliveryId)
    if preparation.message is None:
        return EmailDeliveryResult(
            delivery_id=preparation.delivery_id,
            status=preparation.status,
            retry_at=preparation.retry_at,
        )

    # Preparation committed before network I/O; no database locks span the SMTP session.
    smtpResult = send_smtp_once(preparation.message)
    changedRows = EmailDelivery.objects.filter(
        pk=deliveryId, status=EmailStatus.SENDING
    ).update(
        status=smtpResult.status,
        finished_at=timezone.now(),
        reason_code=smtpResult.reason_code,
    )
    if changedRows != 1:
        raise RuntimeError(
            "The email attempt result could not be recorded; do not resend it."
        )

    return EmailDeliveryResult(delivery_id=deliveryId, status=smtpResult.status)
