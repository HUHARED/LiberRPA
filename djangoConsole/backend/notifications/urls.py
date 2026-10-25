# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .contracts import NotificationAction
from . import views

urlpatterns = [
    path("", views.list_notifications, name="notifications"),
    path(
        "read-all/",
        views.change_notifications,
        {"action": NotificationAction.READ_ALL},
        name="notifications-read-all",
    ),
    path(
        "clear/",
        views.change_notifications,
        {"action": NotificationAction.CLEAR},
        name="notifications-clear",
    ),
    path("<uuid:notificationId>/", views.notification_details, name="notification"),
    path(
        "<uuid:notificationId>/read/",
        views.change_notifications,
        {"action": NotificationAction.READ},
        name="notification-read",
    ),
    path(
        "<uuid:notificationId>/delete/",
        views.change_notifications,
        {"action": NotificationAction.DELETE},
        name="notification-delete",
    ),
]
