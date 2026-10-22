# FileName: delivery.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from typing import cast

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
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
    build_account_deletion_notice,
)
from organizations.models import MemberInvitation
from organizations.invitations import InvitationConflictError, issue_invitation_token
from organizations.emails import (
    build_invitation_email,
    build_organization_deletion_notice,
)
from organizations.limit_emails import build_organization_limits_notice
from organizations.service_emails import build_organization_service_notice
from operations.backup_emails import build_backup_notice

from .contracts import EmailStatus, EmailReasonCode
from .models import (
    EmailType,
    EmailDispatchState,
    EmailDelivery,
    AccountDeletionNotice,
    OrganizationDeletionScheduleNotice,
    OrganizationLimitsNotice,
    RunEmailEvent,
    RunEmailReference,
)
from .recipients import get_eligible_recipients
from .smtp import send_smtp_once

EMAIL_BUDGET_WINDOW = timedelta(hours=24)


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
    intElapsedUnits = max(0, (currentTime - dispatchState.refilled_at) // refillInterval)
    dispatchState.available_units = min(
        limits.emailBurstRecipients, dispatchState.available_units + intElapsedUnits
    )
    if dispatchState.available_units == limits.emailBurstRecipients:
        # Time spent with a full allowance cannot accumulate an extra burst.
        dispatchState.refilled_at = currentTime
    else:
        dispatchState.refilled_at += intElapsedUnits * refillInterval


def _mark_email_not_sent(
    delivery: EmailDelivery, *, reasonCode: EmailReasonCode
) -> EmailPreparationResult:
    """Finish a locked pending request without reserving a recipient unit."""
    delivery.status = EmailStatus.NOT_SENT
    delivery.finished_at = timezone.now()
    delivery.reason_code = reasonCode
    delivery.save(update_fields=["status", "finished_at", "reason_code"])
    return EmailPreparationResult(deliveryId=delivery.id, status=EmailStatus.NOT_SENT)


@sensitive_variables()
@transaction.atomic(durable=True)
def _prepare_email(deliveryId: uuid.UUID) -> EmailPreparationResult:
    """Commit one email reservation and its token before an SMTP attempt.

    Call this from the delivery worker outside any surrounding transaction.
    A message grants one immediate attempt; retryAt schedules only an unattempted request.
    This function does not contact SMTP or recover an earlier Sending request.
    """
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
    intUsedUnits = EmailDelivery.objects.filter(
        attempted_at__gt=currentTime - EMAIL_BUDGET_WINDOW
    ).count()
    if intUsedUnits >= limits.maxEmailRecipientsPer24Hours:
        return _mark_email_not_sent(
            delivery, reasonCode=EmailReasonCode.SMTP_BUDGET_EXHAUSTED
        )

    _refill_email_allowance(dispatchState, currentTime=currentTime, limits=limits)
    if dispatchState.available_units == 0:
        retryAt = dispatchState.refilled_at + timedelta(seconds=limits.emailRefillSeconds)
        return EmailPreparationResult(
            deliveryId=delivery.id,
            status=EmailStatus.PENDING,
            retryAt=retryAt,
        )

    if delivery.email_type == EmailType.RUN:
        from organizations.models import Organization
        from organizations.permissions import is_organization_business_available
        from runs.models import Run
        from .run_email import build_run_email

        reference = (
            RunEmailReference.objects
            .select_related("organization", "recipient")
            .filter(delivery=delivery)
            .first()
        )
        organization = (
            None
            if reference is None
            else Organization.objects
            .select_for_update()
            .filter(pk=reference.organization_id)
            .first()
        )
        if reference is not None:
            reference.recipient = (
                get_eligible_recipients(reference.organization_id)
                .filter(pk=reference.recipient_id, email=delivery.recipient)
                .first()
            )
        if (
            reference is None
            or organization is None
            or reference.recipient is None
            or not is_organization_business_available(organization)
        ):
            return _mark_email_not_sent(
                delivery, reasonCode=EmailReasonCode.RUN_NOT_ELIGIBLE
            )
        run = (
            Run.objects
            .select_related("job__request__organization", "job__department", "assignment")
            .filter(pk=reference.run_id, job__closed_at__isnull=True)
            .first()
        )
        emailEvent = RunEmailEvent(reference.event)
        if run is None or (
            emailEvent != RunEmailEvent.START and run.status != emailEvent
        ):
            return _mark_email_not_sent(
                delivery, reasonCode=EmailReasonCode.RUN_NOT_ELIGIBLE
            )
        attemptedRunEmails = EmailDelivery.objects.filter(
            email_type=EmailType.RUN, attempted_at__isnull=False
        )
        organizationEmails = attemptedRunEmails.filter(
            run_reference__organization=reference.organization
        )
        utcDay = currentTime.astimezone(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if (
            attemptedRunEmails.filter(
                attempted_at__gt=currentTime - EMAIL_BUDGET_WINDOW
            ).count()
            >= limits.maxRunEmailRecipientsPer24Hours
            or organizationEmails.filter(
                attempted_at__gt=currentTime - timedelta(hours=1)
            ).count()
            >= limits.maxRunEmailRecipientsPerOrganizationHour
            or organizationEmails.filter(attempted_at__gte=utcDay).count()
            >= limits.maxRunEmailRecipientsPerOrganizationDay
            or attemptedRunEmails.filter(
                recipient=delivery.recipient,
                attempted_at__gt=currentTime - timedelta(hours=1),
            ).count()
            >= limits.maxRunEmailRecipientsPerAddressHour
        ):
            return _mark_email_not_sent(
                delivery, reasonCode=EmailReasonCode.RUN_BUDGET_EXHAUSTED
            )
        emailMessage = build_run_email(
            run, event=emailEvent, recipient=delivery.recipient
        )
    elif delivery.email_type == EmailType.RUN_RECIPIENT_VERIFICATION:
        from .recipients import build_recipient_verification_email

        try:
            preparedMessage = build_recipient_verification_email(delivery)
        except PermissionDenied:
            preparedMessage = None
        if preparedMessage is None:
            return _mark_email_not_sent(
                delivery, reasonCode=EmailReasonCode.RECIPIENT_NOT_ELIGIBLE
            )
        emailMessage = preparedMessage
    else:
        match delivery.email_type:
            case EmailType.ORGANIZATION_REGISTRATION:
                try:
                    registrationTokenDeliveryInfo = issue_registration_token(
                        delivery.recipient
                    )
                except PermissionDenied:
                    return _mark_email_not_sent(
                        delivery,
                        reasonCode=EmailReasonCode.ORGANIZATION_CREATION_DISABLED,
                    )
                if registrationTokenDeliveryInfo is None:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.REGISTRATION_NOT_ELIGIBLE
                    )
                emailMessage = build_registration_email(registrationTokenDeliveryInfo)
            case EmailType.MEMBER_INVITATION:
                try:
                    invitationDeliveryInfo = issue_invitation_token(delivery)
                except PermissionDenied:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.ORGANIZATION_UNAVAILABLE
                    )
                except InvitationConflictError as e:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode(e.errorCode)
                    )
                except (ValidationError, MemberInvitation.DoesNotExist):
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.INVITATION_NOT_ELIGIBLE
                    )
                if invitationDeliveryInfo is None:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.INVITATION_SUPERSEDED
                    )
                emailMessage = build_invitation_email(invitationDeliveryInfo)
            case EmailType.PASSWORD_RESET:
                resetDeliveryInfo = issue_password_reset_token(delivery)
                if resetDeliveryInfo is None:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.PASSWORD_RESET_NOT_ELIGIBLE
                    )
                emailMessage = build_password_reset_email(resetDeliveryInfo)
            case EmailType.EMAIL_CHANGE_VERIFICATION:
                changeDeliveryInfo = issue_email_change_token(delivery)
                if changeDeliveryInfo is None:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.EMAIL_CHANGE_NOT_ELIGIBLE
                    )
                emailMessage = build_email_change_verification(changeDeliveryInfo)
            case EmailType.EMAIL_CHANGE_NOTICE:
                emailMessage = build_email_change_notice(delivery)
            case EmailType.ACCOUNT_DELETION_NOTICE:
                try:
                    emailMessage = build_account_deletion_notice(delivery)
                except AccountDeletionNotice.DoesNotExist:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.EMAIL_MESSAGE_INVALID
                    )
            case (
                EmailType.ORGANIZATION_DELETION_SCHEDULED_NOTICE
                | EmailType.ORGANIZATION_DELETION_CANCELED_NOTICE
                | EmailType.ORGANIZATION_DELETION_NOTICE
            ):
                try:
                    emailMessage = build_organization_deletion_notice(delivery)
                except OrganizationDeletionScheduleNotice.DoesNotExist:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.EMAIL_MESSAGE_INVALID
                    )
            case EmailType.ORGANIZATION_LIMITS_NOTICE:
                try:
                    emailMessage = build_organization_limits_notice(delivery)
                except OrganizationLimitsNotice.DoesNotExist:
                    return _mark_email_not_sent(
                        delivery, reasonCode=EmailReasonCode.LIMITS_NOTICE_MISSING
                    )
            case (
                EmailType.ORGANIZATION_SUSPENDED_NOTICE
                | EmailType.ORGANIZATION_RESUMED_NOTICE
            ):
                emailMessage = build_organization_service_notice(delivery)
            case EmailType.BACKUP_FAILURE_NOTICE | EmailType.BACKUP_RECOVERY_NOTICE:
                emailMessage = build_backup_notice(delivery)
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
    preparationResult = _prepare_email(deliveryId)
    if preparationResult.message is None:
        return EmailDeliveryResult(
            deliveryId=preparationResult.deliveryId,
            status=preparationResult.status,
            retryAt=preparationResult.retryAt,
        )

    # Preparation committed before network I/O; no database locks span the SMTP session.
    smtpResult = send_smtp_once(preparationResult.message)
    intUpdatedRowCount = EmailDelivery.objects.filter(
        pk=deliveryId, status=EmailStatus.SENDING
    ).update(
        status=smtpResult.status,
        finished_at=timezone.now(),
        reason_code=smtpResult.reasonCode,
    )
    if intUpdatedRowCount != 1:
        raise RuntimeError(
            "The email attempt result could not be recorded; do not resend it."
        )

    return EmailDeliveryResult(deliveryId=deliveryId, status=smtpResult.status)
