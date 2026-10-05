# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from . import views

urlpatterns = [
    path("", views.list_notifications),
    path("read-all/", views.change_notifications, {"action": "read"}),
    path("clear/", views.change_notifications, {"action": "clear"}),
    path("<uuid:notificationId>/", views.notification_details),
    path(
        "<uuid:notificationId>/delete/", views.change_notifications, {"action": "delete"}
    ),
]
