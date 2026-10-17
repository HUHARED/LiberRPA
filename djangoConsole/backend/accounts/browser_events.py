# FileName: browser_events.py
import uuid

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from console_project.db_notifications import (
    NotificationChannel,
    publish_database_notification,
)
from organizations.models import Organization, Department, Membership

from .contracts import BrowserMessageType
from .models import User

_SET_USER_FIELDS = frozenset({
    "email",
    "username",
    "time_zone",
    "password",
    "session_version",
    "is_active",
})
_SET_ORGANIZATION_FIELDS = frozenset({
    "name",
    "suspended_at",
    "deletion_requested_at",
    "deletion_due_at",
    "deletion_started_at",
})


def notify_browser_user(userId: uuid.UUID, event: BrowserMessageType) -> None:
    """Send an invalidation hint, never a credential or a copy of business data."""
    publish_database_notification(NotificationChannel.BROWSER_EVENTS, f"{event}:{userId}")


def _notify_organization_members(organizationId: uuid.UUID) -> None:
    for userId in Membership.objects.filter(organization_id=organizationId).values_list(
        "user_id", flat=True
    ):
        notify_browser_user(userId, BrowserMessageType.SESSION_CHANGED)


@receiver(post_save, sender=User)
def _user_saved(
    *,
    instance: User,
    created: bool,
    raw: bool,
    update_fields: frozenset[str] | None,
    **_kwargs: object,
) -> None:
    # Login timestamp writes do not change the displayed identity or authorization.
    if (
        not raw
        and not created
        and (update_fields is None or _SET_USER_FIELDS.intersection(update_fields))
    ):
        notify_browser_user(instance.pk, BrowserMessageType.SESSION_CHANGED)


@receiver(post_delete, sender=User)
def _user_deleted(*, instance: User, **_kwargs: object) -> None:
    notify_browser_user(instance.pk, BrowserMessageType.SESSION_CHANGED)


@receiver(post_save, sender=Membership)
def _membership_saved(
    *,
    instance: Membership,
    raw: bool,
    **_kwargs: object,
) -> None:
    # NOTE: The membership service saves this row and its bulk department-role edits in one transaction.
    if not raw:
        notify_browser_user(instance.user_id, BrowserMessageType.SESSION_CHANGED)


@receiver(post_save, sender=Organization)
def _organization_saved(
    *,
    instance: Organization,
    created: bool,
    raw: bool,
    update_fields: frozenset[str] | None,
    **_kwargs: object,
) -> None:
    if (
        not raw
        and not created
        and (
            update_fields is None or _SET_ORGANIZATION_FIELDS.intersection(update_fields)
        )
    ):
        _notify_organization_members(instance.pk)


@receiver(post_save, sender=Department)
def _department_saved(*, instance: Department, raw: bool, **_kwargs: object) -> None:
    if not raw:
        _notify_organization_members(instance.organization_id)
