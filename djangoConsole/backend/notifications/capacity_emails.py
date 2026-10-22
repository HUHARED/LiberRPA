# FileName: capacity_emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connection

from operations.capacity_contracts import (
    INT_CAPACITY_WARNING_PERCENT,
    INT_STORAGE_WARNING_BYTES,
    CapacityResource,
    CapacityLevel,
)
from organizations.limits import LIMIT_DEFINITIONS, LimitUnit
from organizations.models import Organization, Membership

from .contracts import EmailStatus
from .models import EmailType, EmailDelivery, CapacityNotice

if TYPE_CHECKING:
    from operations.models import CapacityAlertState


def queue_capacity_notices(
    state: "CapacityAlertState", organization: Organization | None
) -> int:
    """Commit one immutable observation per recipient with the caller's alert-state update."""
    if not connection.in_atomic_block:
        raise RuntimeError(
            "Queue capacity notices inside the capacity-check transaction."
        )
    if state.used is None or state.reserved is None or state.limit is None:
        raise ValueError("A measured capacity warning is required.")

    if organization is None:
        # The platform account has no mailbox; use the existing operator contact.
        listRecipient = [cast(str, settings.CONSOLE_SUPPORT_EMAIL).lower()]
        strOrganizationName = ""
        strTimeZone = "UTC"
    else:
        listRecipient = list(
            Membership.objects
            .filter(
                organization=organization,
                is_org_admin=True,
                user__is_active=True,
                user__is_platform_admin=False,
            )
            .order_by("user_id")
            .values_list("user__email", flat=True)
        )
        strOrganizationName = organization.name
        strTimeZone = organization.default_time_zone

    # An unavailable email worker must not accumulate another copy every day.
    setPendingRecipient = set(
        EmailDelivery.objects.filter(
            organization_id=state.organization_id,
            email_type=EmailType.CAPACITY_NOTICE,
            status__in=[EmailStatus.PENDING, EmailStatus.SENDING],
            capacity_notice__resource=state.resource,
            capacity_notice__level=state.level,
        ).values_list("recipient", flat=True)
    )
    listDelivery = EmailDelivery.objects.bulk_create([
        EmailDelivery(
            organization_id=state.organization_id,
            organization_name=strOrganizationName,
            time_zone=strTimeZone,
            email_type=EmailType.CAPACITY_NOTICE,
            recipient=strRecipient,
            created_at=state.checked_at,
        )
        for strRecipient in listRecipient
        if strRecipient not in setPendingRecipient
    ])
    CapacityNotice.objects.bulk_create([
        CapacityNotice(
            delivery=delivery,
            resource=state.resource,
            level=state.level,
            used=state.used,
            reserved=state.reserved,
            limit=state.limit,
            free_bytes=state.free_bytes,
        )
        for delivery in listDelivery
    ])
    return len(listDelivery)


def build_capacity_notice(delivery: EmailDelivery) -> EmailMessage:
    """Describe recorded capacity values, never later usage or SMTP response text."""
    if delivery.email_type != EmailType.CAPACITY_NOTICE:
        raise ValueError("A capacity notice delivery is required.")
    notice = CapacityNotice.objects.get(delivery_id=delivery.id)
    resource = CapacityResource(notice.resource)
    level = CapacityLevel(notice.level)
    strCheckedAt = delivery.created_at.astimezone(ZoneInfo(delivery.time_zone)).isoformat(
        sep=" ", timespec="seconds"
    )
    strConsoleUrl = cast(str, settings.CONSOLE_URL)

    if resource == CapacityResource.STORAGE_VOLUME:
        if notice.free_bytes is None:
            raise ValueError("A volume notice requires its recorded free space.")
        intFreeBytes = notice.free_bytes
        strSubject = "LiberRPA Console storage is running low"
        strBody = (
            "The volume used for Console file storage is low on free space.\n\n"
            f"Free: {intFreeBytes / 1024**3:,.2f} GiB\n"
            f"Used: {notice.used / 1024**3:,.2f} GiB\n"
            f"Total: {notice.limit / 1024**3:,.2f} GiB\n"
            f"Warning threshold: {INT_STORAGE_WARNING_BYTES / 1024**3:,.2f} GiB\n\n"
            "Review the volume and remove unneeded files through the supported tools. "
            "Do not delete Console storage files directly.\n"
            "On the server, run: python backend/manage.py instance_status\n"
        )
    else:
        definition = next(
            item for item in LIMIT_DEFINITIONS if item.key.value == resource.value
        )

        def _format_value(value: int) -> str:
            if definition.unit == LimitUnit.BYTES:
                return f"{value:,} bytes ({value / 1024**3:,.3f} GiB)"
            return f"{value:,}"

        strReservation = (
            f"Reserved: {_format_value(notice.reserved)}\n"
            if resource == CapacityResource.STORED_BYTES
            else ""
        )
        strReservationNote = (
            "Used and reserved amounts are counted together for this warning. "
            if resource == CapacityResource.STORED_BYTES
            else ""
        )
        strSubject = f"LiberRPA Console capacity: {resource.label}"
        strCondition = (
            "Usage has reached or exceeded the configured limit."
            if level == CapacityLevel.LIMIT_REACHED
            else f"Usage has reached the {INT_CAPACITY_WARNING_PERCENT}% warning threshold."
        )
        strBody = (
            f"{strCondition}\n\n"
            f"Organization: {delivery.organization_name}\n"
            f"Organization ID: {delivery.organization_id}\n"
            f"Resource: {resource.label}\n"
            f"Used: {_format_value(notice.used)}\n"
            f"{strReservation}"
            f"Limit: {_format_value(notice.limit)}\n\n"
            f"{strReservationNote}"
            "Review usage and remove unneeded data through Console. "
            "File and queue growth follows the current limits; eligible Run logs and "
            "history follow their cleanup rules. This notice does not stop running work.\n"
            f"Usage: {strConsoleUrl}/organization-settings/usage-retention\n"
        )
    return EmailMessage(
        subject=strSubject,
        body=(
            f"{strBody}\nChecked at: {strCheckedAt}\nConsole: {strConsoleUrl}\n\n"
            "These values describe the recorded check, not current usage.\n\nLiberRPA Console\n"
        ),
        to=[delivery.recipient],
        reply_to=[cast(str, settings.CONSOLE_SUPPORT_EMAIL)],
    )
