# FileName: password_reset_emails.py
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

from .password_resets import PasswordResetTokenDeliveryInfo


@sensitive_variables()
def build_password_reset_email(
    deliveryInfo: PasswordResetTokenDeliveryInfo,
) -> EmailMessage:
    """Build the private recovery message; delivery and retry rules belong to the worker."""
    consoleUrl = cast(str | None, settings.CONSOLE_URL)
    if consoleUrl is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before preparing email."
        )
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
