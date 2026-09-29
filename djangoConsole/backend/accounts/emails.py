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

from notifications.models import EmailType, EmailDelivery

from .registration import RegistrationTokenDeliveryInfo
from .password_resets import PasswordResetTokenDeliveryInfo
from .email_changes import EmailChangeTokenDeliveryInfo


@sensitive_variables()
def build_registration_email(deliveryInfo: RegistrationTokenDeliveryInfo) -> EmailMessage:
    """Build a private message from an issued token without sending it or accessing the database.

    The delivery process owns current eligibility, budgets, one SMTP attempt, and result recording.
    The caller must not log or return the message body to an anonymous requesting client.
    """
    consoleUrl = cast(str, settings.CONSOLE_URL)

    # Use the configured origin; an incoming request must not choose the email link's host.
    # The browser keeps the fragment out of the initial page request and HTTP access logs.
    verificationUrl = (
        f"{consoleUrl}/create-organization/#{urlencode({'token': deliveryInfo.token})}"
    )
    expiresAtText = deliveryInfo.expiresAt.astimezone(UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    emailBody = (
        "Verify your email to create a LiberRPA Console organization.\n\n"
        "Open this link to complete registration:\n"
        f"{verificationUrl}\n\n"
        f"This link expires at {expiresAtText}.\n"
        "Opening the link does not create an account or use up the link.\n"
        "After successful registration, the link cannot be used again.\n"
        "If a new link is issued, this link stops working.\n\n"
        "If you did not request this email, you can ignore it.\n\n"
        "LiberRPA Console\n"
    )
    return EmailMessage(
        subject="Verify your email for LiberRPA Console",
        body=emailBody,
        to=[deliveryInfo.email],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )


@sensitive_variables()
def build_password_reset_email(
    deliveryInfo: PasswordResetTokenDeliveryInfo,
) -> EmailMessage:
    """Build the private recovery message; delivery and retry rules belong to the worker."""
    consoleUrl = cast(str, settings.CONSOLE_URL)
    # Keep the token in the fragment and use the configured origin, never the request host.
    resetUrl = f"{consoleUrl}/reset-password/#{urlencode({'token': deliveryInfo.token})}"
    expiresAtText = deliveryInfo.expiresAt.astimezone(UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    emailBody = (
        "A password reset was requested for your LiberRPA Console account.\n\n"
        "Open this link to choose a new password:\n"
        f"{resetUrl}\n\n"
        f"This link expires at {expiresAtText}.\n"
        "Opening the link does not change your password or use up the link.\n"
        "After a successful reset, the link cannot be used again.\n"
        "Requesting a new reset link invalidates any earlier link.\n\n"
        "Resetting your password will sign you out of all sessions and revoke your active API keys.\n\n"
        "If you did not request this email, you can ignore it. Your password has not changed.\n\n"
        "LiberRPA Console\n"
    )
    return EmailMessage(
        subject="Reset your LiberRPA Console password",
        body=emailBody,
        to=[deliveryInfo.email],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )


@sensitive_variables()
def build_email_change_verification(
    deliveryInfo: EmailChangeTokenDeliveryInfo,
) -> EmailMessage:
    """Build a private confirmation link for the exact address authorized by the account owner."""
    consoleUrl = cast(str, settings.CONSOLE_URL)
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
    consoleUrl = cast(str, settings.CONSOLE_URL)
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
