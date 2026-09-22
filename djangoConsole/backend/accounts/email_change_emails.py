# FileName: email_change_emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import UTC
from typing import cast
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.views.decorators.debug import sensitive_variables

from notifications.models import EmailDelivery, EmailType

from .email_changes import EmailChangeTokenDeliveryInfo


def _get_console_url() -> str:
    consoleUrl = cast(str | None, settings.CONSOLE_URL)
    if consoleUrl is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before preparing email."
        )
    return consoleUrl


@sensitive_variables()
def build_email_change_verification(
    deliveryInfo: EmailChangeTokenDeliveryInfo,
) -> EmailMessage:
    """Build a private confirmation link for the exact address authorized by the account owner."""
    consoleUrl = _get_console_url()
    # The configured origin and URL fragment keep the token out of request-host input and access logs.
    confirmationUrl = (
        f"{consoleUrl}/confirm-email-change/#{urlencode({'token': deliveryInfo.token})}"
    )
    expiresAtText = deliveryInfo.expiresAt.astimezone(UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    emailBody = (
        "Confirm this address as your new LiberRPA Console sign-in email.\n\n"
        "Open this link, then select Confirm Email Change:\n"
        f"{confirmationUrl}\n\n"
        f"This link expires at {expiresAtText}.\n"
        "Opening the link does not change the account or use up the link.\n"
        "After confirmation, you can sign in with this email and your existing password.\n"
        "Existing sessions stay signed in. A notice will be sent to the previous email address.\n"
        "Requesting another email change invalidates this link.\n\n"
        "If you did not request this change, you can ignore this email.\n\n"
        "LiberRPA Console\n"
    )
    return EmailMessage(
        subject="Confirm your new LiberRPA Console email",
        body=emailBody,
        to=[deliveryInfo.newEmail],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )


@sensitive_variables()
def build_email_change_notice(delivery: EmailDelivery) -> EmailMessage:
    """Describe a committed change using its original recipient and event time."""
    if delivery.email_type != EmailType.EMAIL_CHANGE_NOTICE:
        raise ValueError("An email change notice delivery is required.")
    consoleUrl = _get_console_url()
    changedAtText = delivery.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    # This is a historical notice, so later email changes, account deletion, or organization freezes do not suppress it.
    emailBody = (
        f"The sign-in email for your LiberRPA Console account was changed at {changedAtText}.\n\n"
        "This notice was sent to the address used before that change.\n"
        "If you made this change, no further action is needed.\n"
        "If you did not authorize this change, reply to this email to contact support.\n\n"
        f"Open Console: {consoleUrl}\n\n"
        "LiberRPA Console\n"
    )
    return EmailMessage(
        subject="Your LiberRPA Console sign-in email was changed",
        body=emailBody,
        to=[delivery.recipient],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )
