# FileName: emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import UTC
from typing import cast
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connection
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from notifications.models import (
    EmailType,
    EmailDelivery,
    OrganizationDeletionScheduleNotice,
)

from .models import Organization, Membership
from .invitations import InvitationDeliveryInfo


@sensitive_variables()
def build_invitation_email(deliveryInfo: InvitationDeliveryInfo) -> EmailMessage:
    """Build one private message without contacting SMTP or exposing the token to an administrator."""
    strConsoleUrl = cast(str, settings.CONSOLE_URL)
    # NOTE: Use only the configured origin; fragments stay out of initial HTTP access logs.
    strInvitationUrl = (
        f"{strConsoleUrl}/create-account/#{urlencode({'token': deliveryInfo.token})}"
    )
    strExpiresAtText = deliveryInfo.expiresAt.astimezone(UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    return EmailMessage(
        subject="You are invited to LiberRPA Console",
        body=(
            f"You have been invited to join {deliveryInfo.organizationName} in LiberRPA Console.\n\n"
            "Open this link to create your account and join the organization:\n"
            f"{strInvitationUrl}\n\n"
            f"This link expires at {strExpiresAtText}.\n"
            "Opening the link does not create an account or use up the invitation.\n"
            "The link stops working after registration, revocation, or a new invitation request.\n\n"
            "If you did not expect this invitation, you can ignore it.\n\n"
            "LiberRPA Console\n"
        ),
        to=[deliveryInfo.email],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )


def queue_organization_deletion_notices(organization: Organization) -> None:
    """Queue one lifecycle notice per current member inside the locked change transaction."""
    if not connection.in_atomic_block:
        raise RuntimeError("Queue deletion notices inside the organization transaction.")

    boolScheduled = organization.deletion_requested_at is not None
    if boolScheduled and organization.deletion_due_at is None:
        raise ValueError("Scheduled deletion requires a due time.")
    emailType = (
        EmailType.ORGANIZATION_DELETION_SCHEDULED_NOTICE
        if boolScheduled
        else EmailType.ORGANIZATION_DELETION_CANCELED_NOTICE
    )
    changedAt = organization.deletion_requested_at if boolScheduled else timezone.now()
    listDelivery = EmailDelivery.objects.bulk_create([
        EmailDelivery(
            organization_id=organization.pk,
            organization_name=organization.name,
            time_zone=organization.default_time_zone,
            email_type=emailType,
            recipient=strEmail,
            created_at=changedAt,
        )
        for strEmail in Membership.objects
        .filter(organization=organization, user__is_platform_admin=False)
        .order_by("user_id")
        .values_list("user__email", flat=True)
    ])
    if boolScheduled:
        OrganizationDeletionScheduleNotice.objects.bulk_create([
            OrganizationDeletionScheduleNotice(
                delivery=delivery, deletion_due_at=organization.deletion_due_at
            )
            for delivery in listDelivery
        ])


@sensitive_variables()
def build_organization_deletion_notice(delivery: EmailDelivery) -> EmailMessage:
    """Describe the committed event without reading the current organization or membership."""
    strConsoleUrl = cast(str, settings.CONSOLE_URL)
    displayTimeZone = ZoneInfo(delivery.time_zone)
    strChangedAt = delivery.created_at.astimezone(displayTimeZone).isoformat(
        sep=" ", timespec="seconds"
    )
    match delivery.email_type:
        case EmailType.ORGANIZATION_DELETION_SCHEDULED_NOTICE:
            notice = OrganizationDeletionScheduleNotice.objects.get(
                delivery_id=delivery.id
            )
            strDueAt = notice.deletion_due_at.astimezone(displayTimeZone).isoformat(
                sep=" ", timespec="seconds"
            )
            strSubject = "Your LiberRPA Console organization is scheduled for deletion"
            strEvent = f"Deletion of {delivery.organization_name} was scheduled at {strChangedAt}."
            strImpact = (
                f"Scheduled cleanup time: {strDueAt}.\n"
                "Business operations are paused. "
                "Cleanup removes the organization, its current member accounts, and its Console data.\n"
                "Any active organization administrator can sign in and cancel deletion before cleanup actually starts, even if the scheduled time has passed."
            )
            strConsoleUrl += "/organization-status"
        case EmailType.ORGANIZATION_DELETION_CANCELED_NOTICE:
            strSubject = "Your LiberRPA Console organization deletion was canceled"
            strEvent = f"Deletion of {delivery.organization_name} was canceled at {strChangedAt}."
            strImpact = (
                "The deletion plan has been canceled. "
                "An independent service suspension, if any, remains in place.\n"
                "Previously canceled work and missed scheduled runs do not restart automatically."
            )
            strConsoleUrl += "/organization-status"
        case EmailType.ORGANIZATION_DELETION_NOTICE:
            strSubject = "Your LiberRPA Console organization was deleted"
            strEvent = f"The organization {delivery.organization_name} was deleted at {strChangedAt}."
            strImpact = (
                "The organization, its current member accounts, and its Console data have been removed.\n"
                "This notice was sent to your membership email address recorded before deletion."
            )
        case _:
            raise ValueError("An organization deletion notice delivery is required.")

    return EmailMessage(
        subject=strSubject,
        body=(
            f"{strEvent}\n\n"
            f"Organization ID: {delivery.organization_id}\n\n"
            f"{strImpact}\n\n"
            "This does not remove files on client devices or confirm that remote processes have stopped.\n"
            "If you have questions, reply to this email to contact support.\n"
            f"Console: {strConsoleUrl}\n\n"
            "LiberRPA Console\n"
        ),
        to=[delivery.recipient],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )
