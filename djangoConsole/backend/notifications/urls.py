# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .contracts import NotificationAction
from . import views

urlpatterns = [
    path("", views.list_notifications),
    path(
        "read-all/", views.change_notifications, {"action": NotificationAction.READ_ALL}
    ),
    path("clear/", views.change_notifications, {"action": NotificationAction.CLEAR}),
    path("<uuid:notificationId>/", views.notification_details),
    path(
        "<uuid:notificationId>/read/",
        views.change_notifications,
        {"action": NotificationAction.READ},
    ),
    path(
        "<uuid:notificationId>/delete/",
        views.change_notifications,
        {"action": NotificationAction.DELETE},
    ),
]
