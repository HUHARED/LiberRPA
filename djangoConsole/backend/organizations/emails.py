# FileName: emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import UTC
from typing import cast
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMessage
from django.views.decorators.debug import sensitive_variables

from notifications.models import EmailDelivery, EmailType, OrganizationDeletionNotice

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


@sensitive_variables()
def build_organization_deletion_notice(delivery: EmailDelivery) -> EmailMessage:
    """Build a historical completion notice using only the committed deletion snapshot."""
    if delivery.email_type != EmailType.ORGANIZATION_DELETION_NOTICE:
        raise ValueError("An organization deletion notice delivery is required.")
    strConsoleUrl = cast(str, settings.CONSOLE_URL)
    notice = OrganizationDeletionNotice.objects.get(delivery_id=delivery.id)
    strCompletedAtText = delivery.created_at.astimezone(UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    strEmailBody = (
        f"The LiberRPA Console organization {notice.organization_name} was deleted at {strCompletedAtText}.\n\n"
        f"Organization ID: {notice.organization_id}\n"
        "The organization, its current member accounts, and its Console data have been removed.\n"
        "This notice was sent to your membership email address recorded before deletion.\n"
        "This does not remove files on client devices or confirm that remote processes have stopped.\n\n"
        "If you have questions, reply to this email to contact support.\n"
        f"Console: {strConsoleUrl}\n\n"
        "LiberRPA Console\n"
    )
    return EmailMessage(
        subject="Your LiberRPA Console organization was deleted",
        body=strEmailBody,
        to=[delivery.recipient],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )
