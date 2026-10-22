# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from accounts.contracts import BrowserMessageType
from accounts.browser_events import notify_browser_user
from console_project.contracts import MessageResponse
from console_project.http import parse_json_request
from organizations.http import get_request_membership, lock_request_write_access
from organizations.permissions import AccessChannel, build_organization_access
from organizations.rate_limits import RequestBudget, request_budget

from .contracts import (
    NotificationAction,
    NotificationResponse,
    NotificationListResponse,
    NotificationDetailsRecordResponse,
    NotificationDetailsResponse,
    NotificationReadResponse,
    EmptyRequest,
)
from .http import handle_notification_errors
from .models import Notification
from .services import prune_notifications


@request_budget(RequestBudget.INDEPENDENT)
@never_cache
@require_http_methods(["GET"])
@handle_notification_errors
def list_notifications(request: HttpRequest) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        prune_notifications(access.actor.pk)
    query = Notification.objects.filter(
        user=access.actor, organization=access.organization
    ).order_by("-created_at", "-id")
    listNotification = [
        NotificationResponse(
            id=notification.pk,
            title=notification.title,
            created_at=notification.created_at,
            read_at=notification.read_at,
        )
        for notification in query
    ]
    response = NotificationListResponse(
        notifications=listNotification,
        unread_count=sum(
            notification.read_at is None for notification in listNotification
        ),
    )
    return JsonResponse(response.model_dump(mode="json"))


@request_budget(RequestBudget.INDEPENDENT)
@never_cache
@require_http_methods(["GET"])
@handle_notification_errors
def notification_details(request: HttpRequest, notificationId: uuid.UUID) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    access = build_organization_access(membership, channel=AccessChannel.SESSION)
    notification = Notification.objects.get(
        pk=notificationId, user=access.actor, organization=access.organization
    )
    response = NotificationDetailsResponse(
        notification=NotificationDetailsRecordResponse(
            id=notification.pk,
            title=notification.title,
            created_at=notification.created_at,
            read_at=notification.read_at,
            detail=notification.detail,
        )
    )
    return JsonResponse(response.model_dump(mode="json"))


@request_budget(RequestBudget.INDEPENDENT)
@never_cache
@require_POST
@handle_notification_errors
def change_notifications(
    request: HttpRequest,
    action: NotificationAction,
    notificationId: uuid.UUID | None = None,
) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    form = parse_json_request(request, EmptyRequest)
    if isinstance(form, JsonResponse):
        return form
    readResponse: NotificationReadResponse | None = None
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        query = Notification.objects.filter(
            user=access.actor, organization=access.organization
        )
        match action:
            case NotificationAction.READ:
                if notificationId is None:
                    raise ValidationError("Select a notification to mark as read.")
                notification = query.select_for_update().get(pk=notificationId)
                readAt = notification.read_at
                intChanged = 0
                if readAt is None:
                    readAt = timezone.now()
                    notification.read_at = readAt
                    notification.save(update_fields=["read_at"])
                    intChanged = 1
                readResponse = NotificationReadResponse(
                    id=notification.pk, read_at=readAt
                )
            case NotificationAction.READ_ALL:
                intChanged = query.filter(read_at__isnull=True).update(
                    read_at=timezone.now()
                )
            case NotificationAction.DELETE:
                if notificationId is None:
                    raise ValidationError("Select a notification to delete.")
                intChanged, _ = query.get(pk=notificationId).delete()
            case NotificationAction.CLEAR:
                intChanged, _ = query.delete()
            case _:
                raise ValidationError("Unsupported notification action.")
        if intChanged:
            notify_browser_user(access.actor.pk, BrowserMessageType.NOTIFICATIONS_CHANGED)
    if readResponse is not None:
        return JsonResponse(readResponse.model_dump(mode="json"))
    return JsonResponse(
        MessageResponse(message="Notifications updated.").model_dump(mode="json")
    )
