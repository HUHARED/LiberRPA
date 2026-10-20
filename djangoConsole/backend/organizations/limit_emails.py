# FileName: limit_emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connection
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from notifications.models import EmailDelivery, EmailType, OrganizationLimitsNotice

from .limits import LIMIT_DEFINITIONS, LimitUnit
from .models import Membership, Organization


def queue_organization_limits_notices(
    organization: Organization, changes: dict[str, dict[str, int | None]]
) -> None:
    """Queue one summary per active administrator in the caller's locked organization write."""
    if not changes:
        return
    if not connection.in_atomic_block:
        raise RuntimeError("Queue limit notices inside the limit-change transaction.")

    currentTime = timezone.now()
    listDelivery = EmailDelivery.objects.bulk_create([
        EmailDelivery(
            organization_id=organization.pk,
            email_type=EmailType.ORGANIZATION_LIMITS_NOTICE,
            recipient=strEmail,
            created_at=currentTime,
        )
        for strEmail in Membership.objects
        .filter(organization=organization, is_org_admin=True, user__is_active=True)
        .order_by("user_id")
        .values_list("user__email", flat=True)
    ])
    OrganizationLimitsNotice.objects.bulk_create([
        OrganizationLimitsNotice(
            delivery=delivery,
            organization_id=organization.pk,
            organization_name=organization.name,
            changes=changes,
        )
        for delivery in listDelivery
    ])


@sensitive_variables()
def build_organization_limits_notice(delivery: EmailDelivery) -> EmailMessage:
    """Build a historical summary without rechecking organization state or current limits."""
    if delivery.email_type != EmailType.ORGANIZATION_LIMITS_NOTICE:
        raise ValueError("An organization limits notice delivery is required.")
    notice = OrganizationLimitsNotice.objects.get(delivery_id=delivery.id)

    def formatValue(value: int, unit: LimitUnit) -> str:
        if unit == LimitUnit.BYTES:
            for strUnit, intUnitBytes in (
                ("GiB", 1024**3),
                ("MiB", 1024**2),
                ("KiB", 1024),
            ):
                if value > 0 and value % intUnitBytes == 0:
                    return f"{value // intUnitBytes:,} {strUnit}"
            return f"{value:,} bytes"
        if unit == LimitUnit.PER_MINUTE:
            return f"{value:,} per minute"
        return f"{value:,}"

    listChangeLine: list[str] = []
    for definition in LIMIT_DEFINITIONS:
        if definition.configName not in notice.changes:
            continue
        change = notice.changes[definition.configName]
        strBeforeSource = "Default" if change["before"] is None else "Override"
        strAfterSource = "Default" if change["after"] is None else "Override"
        listChangeLine.append(
            f"{definition.label}: "
            f"{formatValue(change['before_limit'], definition.unit)} ({strBeforeSource})"
            " -> "
            f"{formatValue(change['after_limit'], definition.unit)} ({strAfterSource})"
        )

    strChangeSummary = "\n".join(listChangeLine)
    return EmailMessage(
        subject="Your LiberRPA Console organization limits changed",
        body=(
            f"The limits for {notice.organization_name} were updated.\n\n"
            f"Organization ID: {notice.organization_id}\n\n"
            f"{strChangeSummary}\n\n"
            "Default values follow the instance settings. Overrides stay fixed until changed or reset.\n\n"
            "Lower limits may restrict new activity or storage growth. Eligible logs and Run history "
            "may be cleaned up under their retention rules. Business files and queue items are kept, "
            "and accepted Jobs are not canceled.\n\n"
            f"Console: {cast(str, settings.CONSOLE_URL)}/organization-settings/usage-retention\n\n"
            "LiberRPA Console\n"
        ),
        to=[delivery.recipient],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )
