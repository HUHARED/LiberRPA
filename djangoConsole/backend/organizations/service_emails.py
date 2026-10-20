# FileName: service_emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import UTC
from typing import cast

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connection
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from notifications.models import EmailType, EmailDelivery

from .models import Organization, Membership


def queue_organization_service_notices(organization: Organization) -> None:
    """Queue a committed service transition for its current active administrators."""
    if not connection.in_atomic_block:
        raise RuntimeError("Queue service notices inside the service-change transaction.")

    emailType = (
        EmailType.ORGANIZATION_SUSPENDED_NOTICE
        if organization.suspended_at is not None
        else EmailType.ORGANIZATION_RESUMED_NOTICE
    )
    currentTime = timezone.now()
    EmailDelivery.objects.bulk_create([
        EmailDelivery(
            organization_id=organization.pk,
            organization_name=organization.name,
            email_type=emailType,
            recipient=strEmail,
            created_at=currentTime,
        )
        for strEmail in Membership.objects
        .filter(
            organization=organization,
            is_org_admin=True,
            user__is_active=True,
            user__is_platform_admin=False,
        )
        .order_by("user_id")
        .values_list("user__email", flat=True)
    ])


@sensitive_variables()
def build_organization_service_notice(delivery: EmailDelivery) -> EmailMessage:
    """Build the recorded event without rechecking current organization or account state."""
    match delivery.email_type:
        case EmailType.ORGANIZATION_SUSPENDED_NOTICE:
            strAction = "suspended"
            strImpact = (
                "The organization cannot use Console business features while suspended. "
                "This does not confirm that processes on Executor devices have stopped."
            )
        case EmailType.ORGANIZATION_RESUMED_NOTICE:
            strAction = "resumed"
            strImpact = (
                "The suspension has been lifted. A pending organization deletion still blocks business activity. "
                "Previously canceled work and missed scheduled runs do not restart automatically."
            )
        case _:
            raise ValueError("An organization service notice delivery is required.")

    strChangedAt = delivery.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return EmailMessage(
        subject=f"Your LiberRPA Console organization service was {strAction}",
        body=(
            f"Service for {delivery.organization_name} was {strAction} at {strChangedAt}.\n\n"
            f"Organization ID: {delivery.organization_id}\n\n"
            f"{strImpact}\n\n"
            "If you have questions, reply to this email to contact support.\n"
            f"Console: {cast(str, settings.CONSOLE_URL)}/organization-status\n\n"
            "LiberRPA Console\n"
        ),
        to=[delivery.recipient],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )
