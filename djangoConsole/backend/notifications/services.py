# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from accounts.models import User
from organizations.models import DepartmentRole, Membership
from organizations.permissions import (
    AccessChannel,
    get_authorized_departments,
    resolve_organization_access,
)

from .models import Notification


def prune_notifications(userId: uuid.UUID) -> None:
    query = Notification.objects.filter(user_id=userId)
    query.filter(
        created_at__lt=timezone.now()
        - timedelta(days=settings.CONSOLE_LIMITS.notificationRetentionDays)
    ).delete()
    listOldId = list(
        query.order_by("-created_at", "-id").values_list("id", flat=True)[
            settings.CONSOLE_LIMITS.maxNotificationsPerAccount :
        ]
    )
    if listOldId:
        query.filter(pk__in=listOldId).delete()


def notify_prestart_failure(
    *,
    organizationId: uuid.UUID,
    departmentId: uuid.UUID,
    creatorId: uuid.UUID | None,
    title: str,
    detail: str,
    eventKey: str,
) -> None:
    """Use current creator access; only an absent creator falls back to current admins."""
    if creatorId is None or not User.objects.filter(pk=creatorId).exists():
        listUserId = list(
            Membership.objects.filter(
                organization_id=organizationId, is_org_admin=True, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    else:
        try:
            access = resolve_organization_access(
                actorId=creatorId,
                organizationId=organizationId,
                channel=AccessChannel.SESSION,
            )
            if (
                not get_authorized_departments(
                    access, requiredRole=DepartmentRole.OPERATOR
                )
                .filter(pk=departmentId)
                .exists()
            ):
                return
        except PermissionDenied:
            return
        listUserId = [creatorId]
    strDetail = detail.encode("utf-8")[:8192].decode("utf-8", errors="ignore")
    for userId in listUserId:
        Notification.objects.get_or_create(
            user_id=userId,
            event_key=eventKey,
            defaults={
                "organization_id": organizationId,
                "title": title[:200],
                "detail": strDetail,
            },
        )
        prune_notifications(userId)
