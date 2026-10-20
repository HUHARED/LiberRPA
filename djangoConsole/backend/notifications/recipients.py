# FileName: recipients.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db.models import Case, CharField, Exists, OuterRef, QuerySet, Value, When
from django.utils import timezone

from operations.audit import record_audit
from organizations.limits import get_organization_limits
from organizations.models import Organization, Membership
from organizations.permissions import (
    OrganizationAccessContext,
    require_organization_admin,
    require_organization_business_available,
)

from .contracts import EmailStatus, EmailReasonCode, RunEmailRecipientStatus
from .models import (
    EmailType,
    EmailDelivery,
    RunEmailRecipient,
    RunRecipientVerification,
    RunEmailReference,
)

_STR_TOKEN_SALT = "console.run-email-recipient"
_INT_TOKEN_AGE_SECONDS = 86400


def get_recipient_query(organizationId: uuid.UUID) -> QuerySet[RunEmailRecipient]:
    """Derive eligibility from current membership without granting permanent verification."""
    currentMembers = Membership.objects.filter(
        organization_id=organizationId,
        user__email=OuterRef("email"),
        user__is_active=True,
    )
    return RunEmailRecipient.objects.filter(organization_id=organizationId).annotate(
        status=Case(
            When(Exists(currentMembers), then=Value(RunEmailRecipientStatus.MEMBER)),
            When(
                verified_at__isnull=False,
                then=Value(RunEmailRecipientStatus.VERIFIED),
            ),
            default=Value(RunEmailRecipientStatus.PENDING),
            output_field=CharField(),
        )
    )


def get_eligible_recipients(organizationId: uuid.UUID) -> QuerySet[RunEmailRecipient]:
    return get_recipient_query(organizationId).exclude(
        status=RunEmailRecipientStatus.PENDING
    )


def register_member_recipient(organizationId: uuid.UUID, email: str) -> None:
    """Register the current account address within its membership write transaction."""
    # Keep an existing address ID, notes and independent verification when a member joins.
    RunEmailRecipient.objects.get_or_create(organization_id=organizationId, email=email)


def queue_recipient_verification(
    recipient: RunEmailRecipient, *, organizationName: str
) -> None:
    delivery = EmailDelivery.objects.create(
        organization_id=recipient.organization_id,
        organization_name=organizationName,
        email_type=EmailType.RUN_RECIPIENT_VERIFICATION,
        recipient=recipient.email,
    )
    RunRecipientVerification.objects.create(
        delivery=delivery, recipient=recipient, verification_id=recipient.verification_id
    )


def create_recipient(
    access: OrganizationAccessContext, *, email: str, notes: str
) -> RunEmailRecipient:
    require_organization_admin(access)
    strEmail = email.strip().lower()
    validate_email(strEmail)
    if len(strEmail) > 254 or len(notes) > 2000 or "\x00" in notes:
        raise ValidationError("The email address or notes are too long or invalid.")
    if RunEmailRecipient.objects.filter(
        organization=access.organization, email=strEmail
    ).exists():
        raise ValidationError(
            "This email address is already registered for this organization."
        )
    limits = get_organization_limits(access.organization)
    if (
        get_recipient_query(access.organization.pk)
        .exclude(status=RunEmailRecipientStatus.MEMBER)
        .count()
        >= limits.maxRunEmailAddressesPerOrganization
    ):
        raise ValidationError(
            "This organization has reached its Run email address limit."
        )
    recipient = RunEmailRecipient.objects.create(
        organization=access.organization, email=strEmail, notes=notes
    )
    recipient = get_recipient_query(access.organization.pk).get(pk=recipient.pk)
    if recipient.status == RunEmailRecipientStatus.PENDING:
        queue_recipient_verification(
            recipient, organizationName=access.organization.name
        )
    record_audit(
        "run_email_recipient.create",
        actor=access.actor,
        organization=access.organization,
        target=recipient,
    )
    return recipient


def resend_recipient_verification(
    recipient: RunEmailRecipient, *, organizationName: str
) -> None:
    if recipient.status == RunEmailRecipientStatus.MEMBER:
        raise ValidationError("Member email addresses do not need verification.")
    if recipient.status == RunEmailRecipientStatus.VERIFIED:
        raise ValidationError("This email address is already verified.")
    currentTime = timezone.now()
    if currentTime < recipient.verification_requested_at + timedelta(
        seconds=settings.CONSOLE_LIMITS.emailResendSeconds
    ):
        raise ValidationError("Please wait before requesting another confirmation email.")
    recipient.verification_id = uuid.uuid4()
    recipient.verification_requested_at = currentTime
    recipient.save(update_fields=["verification_id", "verification_requested_at"])
    queue_recipient_verification(recipient, organizationName=organizationName)


def get_recipient_references(recipient: RunEmailRecipient) -> list[dict]:
    from packages.models import Package
    from schedules.models import Schedule
    from runs.contracts import JobState
    from runs.models import Job

    strId = str(recipient.pk)
    listReference = []
    for package in Package.objects.filter(
        department__organization_id=recipient.organization_id,
        run_email__recipient_ids__contains=[strId],
    ).select_related("department"):
        listReference.append({
            "kind": "package",
            "id": str(package.pk),
            "name": f"{package.project_name} {package.project_version}",
            "department": package.department.name,
        })
    for schedule in Schedule.objects.filter(
        department__organization_id=recipient.organization_id,
        deleted_at__isnull=True,
        run_email__recipient_ids__contains=[strId],
    ).select_related("department"):
        listReference.append({
            "kind": "schedule",
            "id": str(schedule.pk),
            "name": schedule.name,
            "department": schedule.department.name,
        })
    if (
        Job.objects
        .filter(
            request__organization_id=recipient.organization_id,
            run_snapshot__run_email__recipient_ids__contains=[strId],
        )
        .exclude(state=JobState.FINISHED)
        .exists()
    ):
        listReference.append({
            "kind": "job",
            "name": "An unfinished Job still needs this address.",
        })
    if RunEmailReference.objects.filter(
        recipient=recipient,
        delivery__status__in=[EmailStatus.PENDING, EmailStatus.SENDING],
    ).exists():
        listReference.append({
            "kind": "delivery",
            "name": "An unfinished Run email delivery still needs this address.",
        })
    return listReference


def delete_recipient(recipient: RunEmailRecipient) -> None:
    if recipient.status == RunEmailRecipientStatus.MEMBER:
        raise ValidationError(
            "Current member email addresses are available automatically."
        )
    EmailDelivery.objects.filter(
        runrecipientverification__recipient=recipient, status=EmailStatus.PENDING
    ).update(
        status=EmailStatus.NOT_SENT,
        finished_at=timezone.now(),
        reason_code=EmailReasonCode.RECIPIENT_NOT_ELIGIBLE,
    )
    recipient.delete()


def load_verification_recipient(
    token: str, *, forUpdate: bool = False
) -> RunEmailRecipient:
    try:
        dictToken = signing.loads(
            token, salt=_STR_TOKEN_SALT, max_age=_INT_TOKEN_AGE_SECONDS
        )
        recipientId = uuid.UUID(dictToken["recipient_id"])
        verificationId = uuid.UUID(dictToken["verification_id"])
        query = RunEmailRecipient.objects.select_related("organization")
        if forUpdate:
            query = query.select_for_update(of=("self",))
        recipient = query.get(pk=recipientId, verification_id=verificationId)
    except (
        signing.BadSignature,
        KeyError,
        TypeError,
        ValueError,
        RunEmailRecipient.DoesNotExist,
    ):
        raise ValidationError(
            "This confirmation link is invalid, expired, or replaced."
        ) from None
    require_organization_business_available(recipient.organization)
    return recipient


def build_recipient_verification_email(delivery: EmailDelivery) -> EmailMessage | None:
    reference = (
        RunRecipientVerification.objects
        .select_related("recipient__organization")
        .filter(delivery=delivery)
        .first()
    )
    if reference is None:
        return None
    if (
        not Organization.objects
        .select_for_update()
        .filter(pk=reference.recipient.organization_id)
        .exists()
    ):
        return None
    recipient = (
        get_recipient_query(reference.recipient.organization_id)
        .select_related("organization")
        .filter(pk=reference.recipient_id)
        .first()
    )
    if recipient is None:
        return None
    if (
        recipient.status != RunEmailRecipientStatus.PENDING
        or recipient.verification_id != reference.verification_id
    ):
        return None
    require_organization_business_available(recipient.organization)
    strToken = signing.dumps(
        {
            "recipient_id": str(recipient.pk),
            "verification_id": str(recipient.verification_id),
        },
        salt=_STR_TOKEN_SALT,
    )
    strUrl = f"{settings.CONSOLE_URL}/verify-run-email/#{urlencode({'token': strToken})}"
    return EmailMessage(
        subject="Confirm Run emails from LiberRPA Console",
        body=f"{recipient.organization.name} wants to send automation Run emails to this address.\n\nOpen the link and confirm that you want to receive these messages:\n{strUrl}\n\nThis link expires in 24 hours. Opening it does not confirm consent.\nIf you did not expect this email, you can ignore it.",
        to=[recipient.email],
        reply_to=[settings.CONSOLE_SUPPORT_EMAIL],
    )
