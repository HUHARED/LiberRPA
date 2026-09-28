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
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from accounts.registration import issue_registration_token
from accounts.password_resets import issue_password_reset_token
from accounts.email_changes import issue_email_change_token
from accounts.emails import (
    build_registration_email,
    build_password_reset_email,
    build_email_change_verification,
    build_email_change_notice,
)
from organizations.models import MemberInvitation
from organizations.invitations import InvitationConflictError, issue_invitation_token
from organizations.emails import (
    build_invitation_email,
    build_organization_deletion_notice,
)

from .models import (
    EmailDelivery,
    EmailDispatchState,
    EmailStatus,
    EmailType,
    OrganizationDeletionNotice,
)
from .smtp import send_smtp_once

_EMAIL_BUDGET_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class EmailPreparationResult:
    """Private worker result; a prepared message must never be returned through a public API."""

    deliveryId: uuid.UUID
    status: EmailStatus
    message: EmailMessage | None = field(default=None, repr=False)
    retryAt: datetime | None = None


@dataclass(frozen=True)
class EmailDeliveryResult:
    """Worker progress without the prepared message or its secret token."""

    deliveryId: uuid.UUID
    status: EmailStatus
    retryAt: datetime | None = None


def _refill_email_allowance(
    dispatchState: EmailDispatchState, *, currentTime: datetime, limits: LimitsConfig
) -> None:
    """Update the already locked rate state in memory, preserving partial refill intervals."""
    refillInterval = timedelta(seconds=limits.emailRefillSeconds)
    elapsedUnits = max(0, (currentTime - dispatchState.refilled_at) // refillInterval)
    dispatchState.available_units = min(
        limits.emailBurstRecipients, dispatchState.available_units + elapsedUnits
    )
    if dispatchState.available_units == limits.emailBurstRecipients:
        # Time spent with a full allowance cannot accumulate an extra burst.
        dispatchState.refilled_at = currentTime
    else:
        dispatchState.refilled_at += elapsedUnits * refillInterval


def _mark_email_not_sent(
    delivery: EmailDelivery, *, reasonCode: str
) -> EmailPreparationResult:
    """Finish a locked pending request without reserving a recipient unit."""
    delivery.status = EmailStatus.NOT_SENT
    delivery.finished_at = timezone.now()
    delivery.reason_code = reasonCode
    delivery.save(update_fields=["status", "finished_at", "reason_code"])
    return EmailPreparationResult(deliveryId=delivery.id, status=EmailStatus.NOT_SENT)


@sensitive_variables()
@transaction.atomic(durable=True)
def prepare_email(deliveryId: uuid.UUID) -> EmailPreparationResult:
    """Commit one email reservation and its token before an SMTP attempt.

    Call this from the delivery worker outside any surrounding transaction.
    A message grants one immediate attempt; retryAt schedules only an unattempted request.
    This function does not contact SMTP or recover an earlier Sending request.
    """
    if settings.CONSOLE_URL is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before preparing email."
        )

    delivery = EmailDelivery.objects.select_for_update().get(pk=deliveryId)
    if delivery.email_type not in EmailType.values:
        raise ValueError("Unsupported email type.")
    if delivery.status != EmailStatus.PENDING:
        return EmailPreparationResult(
            deliveryId=delivery.id, status=EmailStatus(delivery.status)
        )

    # All mail types must take this shared lock before reserving SMTP capacity.
    # NOTE: Lock delivery and dispatch before the purpose-specific proof locks.
    # Registration takes token then policy; invitations, recovery, and email changes take organization first.
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    dispatchState, _ = EmailDispatchState.objects.select_for_update().get_or_create(
        pk=1,
        defaults={"available_units": limits.emailBurstRecipients},
    )
    currentTime = timezone.now()
    usedUnits = EmailDelivery.objects.filter(
        attempted_at__gt=currentTime - _EMAIL_BUDGET_WINDOW
    ).count()
    if usedUnits >= limits.maxEmailRecipientsPer24Hours:
        return _mark_email_not_sent(delivery, reasonCode="smtp_budget_exhausted")

    _refill_email_allowance(dispatchState, currentTime=currentTime, limits=limits)
    if dispatchState.available_units == 0:
        retryAt = dispatchState.refilled_at + timedelta(seconds=limits.emailRefillSeconds)
        return EmailPreparationResult(
            deliveryId=delivery.id,
            status=EmailStatus.PENDING,
            retryAt=retryAt,
        )

    match delivery.email_type:
        case EmailType.ORGANIZATION_REGISTRATION:
            try:
                registrationTokenDeliveryInfo = issue_registration_token(
                    delivery.recipient
                )
            except PermissionDenied:
                return _mark_email_not_sent(
                    delivery, reasonCode="organization_creation_disabled"
                )
            if registrationTokenDeliveryInfo is None:
                return _mark_email_not_sent(
                    delivery, reasonCode="registration_not_eligible"
                )
            emailMessage = build_registration_email(registrationTokenDeliveryInfo)
        case EmailType.MEMBER_INVITATION:
            try:
                invitationDeliveryInfo = issue_invitation_token(delivery)
            except PermissionDenied:
                return _mark_email_not_sent(
                    delivery, reasonCode="organization_unavailable"
                )
            except InvitationConflictError as e:
                return _mark_email_not_sent(delivery, reasonCode=e.errorCode)
            except (ValidationError, MemberInvitation.DoesNotExist):
                return _mark_email_not_sent(
                    delivery, reasonCode="invitation_not_eligible"
                )
            if invitationDeliveryInfo is None:
                return _mark_email_not_sent(delivery, reasonCode="invitation_superseded")
            emailMessage = build_invitation_email(invitationDeliveryInfo)
        case EmailType.PASSWORD_RESET:
            resetDeliveryInfo = issue_password_reset_token(delivery)
            if resetDeliveryInfo is None:
                return _mark_email_not_sent(
                    delivery, reasonCode="password_reset_not_eligible"
                )
            emailMessage = build_password_reset_email(resetDeliveryInfo)
        case EmailType.EMAIL_CHANGE_VERIFICATION:
            changeDeliveryInfo = issue_email_change_token(delivery)
            if changeDeliveryInfo is None:
                return _mark_email_not_sent(
                    delivery, reasonCode="email_change_not_eligible"
                )
            emailMessage = build_email_change_verification(changeDeliveryInfo)
        case EmailType.EMAIL_CHANGE_NOTICE:
            emailMessage = build_email_change_notice(delivery)
        case EmailType.ORGANIZATION_DELETION_NOTICE:
            try:
                emailMessage = build_organization_deletion_notice(delivery)
            except OrganizationDeletionNotice.DoesNotExist:
                return _mark_email_not_sent(
                    delivery, reasonCode="deletion_notice_missing"
                )
        case _:
            raise ValueError("Unsupported email type.")
    attemptedAt = timezone.now()
    # The dispatch lock prevents other reservations while token or policy locks are awaited.
    # Budget usage cannot grow here; refresh only the rate allowance and attempt timestamp.
    _refill_email_allowance(dispatchState, currentTime=attemptedAt, limits=limits)
    dispatchState.available_units -= 1
    dispatchState.save(update_fields=["available_units", "refilled_at"])

    delivery.status = EmailStatus.SENDING
    delivery.attempted_at = attemptedAt
    delivery.save(update_fields=["status", "attempted_at"])
    # The token digest, budget reservation, and Sending state commit together.
    # Never release the reservation after an SMTP failure or an uncertain outcome.
    return EmailPreparationResult(
        deliveryId=delivery.id, status=EmailStatus.SENDING, message=emailMessage
    )


@sensitive_variables()
def deliver_email(deliveryId: uuid.UUID) -> EmailDeliveryResult:
    """Prepare, attempt SMTP once, and record the outcome without holding network-time locks.

    Call outside any surrounding transaction; preparation enforces its own commit boundary.
    A repeated call for a Sending or finished record does not send the message again.
    If result persistence fails, leave Sending for worker recovery; never repeat SMTP.
    """
    preparationResult = prepare_email(deliveryId)
    if preparationResult.message is None:
        return EmailDeliveryResult(
            deliveryId=preparationResult.deliveryId,
            status=preparationResult.status,
            retryAt=preparationResult.retryAt,
        )

    # Preparation committed before network I/O; no database locks span the SMTP session.
    smtpResult = send_smtp_once(preparationResult.message)
    updatedRowCount = EmailDelivery.objects.filter(
        pk=deliveryId, status=EmailStatus.SENDING
    ).update(
        status=smtpResult.status,
        finished_at=timezone.now(),
        reason_code=smtpResult.reasonCode,
    )
    if updatedRowCount != 1:
        raise RuntimeError(
            "The email attempt result could not be recorded; do not resend it."
        )

    return EmailDeliveryResult(deliveryId=deliveryId, status=smtpResult.status)
