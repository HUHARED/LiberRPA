# FileName: deletion_emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import UTC
from typing import cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.views.decorators.debug import sensitive_variables

from notifications.models import EmailDelivery, EmailType, OrganizationDeletionNotice


@sensitive_variables()
def build_organization_deletion_notice(delivery: EmailDelivery) -> EmailMessage:
    """Build a historical completion notice using only the committed deletion snapshot."""
    if delivery.email_type != EmailType.ORGANIZATION_DELETION_NOTICE:
        raise ValueError("An organization deletion notice delivery is required.")
    consoleUrl = cast(str | None, settings.CONSOLE_URL)
    if consoleUrl is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before preparing email."
        )
    notice = OrganizationDeletionNotice.objects.get(delivery_id=delivery.id)
    completedAtText = delivery.created_at.astimezone(UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    emailBody = (
        f"The LiberRPA Console organization {notice.organization_name} was deleted at {completedAtText}.\n\n"
        f"Organization ID: {notice.organization_id}\n"
        "The organization, its current member accounts, and its Console data have been removed.\n"
        "This notice was sent to your membership email address recorded before deletion.\n"
        "This does not remove files on client devices or confirm that remote processes have stopped.\n\n"
        "If you have questions, reply to this email to contact support.\n"
        f"Console: {consoleUrl}\n\n"
        "LiberRPA Console\n"
    )
    return EmailMessage(
        subject="Your LiberRPA Console organization was deleted",
        body=emailBody,
        to=[delivery.recipient],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )
