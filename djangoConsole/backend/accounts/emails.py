# FileName: emails.py
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

from .registration import RegistrationTokenDeliveryInfo


@sensitive_variables()
def build_registration_email(deliveryInfo: RegistrationTokenDeliveryInfo) -> EmailMessage:
    """Build a private message from an issued token without sending it or accessing the database.

    The delivery process owns current eligibility, budgets, one SMTP attempt, and result recording.
    The caller must not log or return the message body to an anonymous requesting client.
    """
    consoleUrl = cast(str | None, settings.CONSOLE_URL)
    if consoleUrl is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before preparing email."
        )

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
