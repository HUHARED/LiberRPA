# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from . import views

urlpatterns = [
    path("", views.list_or_create_schedules, name="schedules"),
    path("preview/", views.preview_schedule, name="schedule-preview"),
    path("<uuid:scheduleId>/", views.get_or_update_schedule, name="schedule"),
    path(
        "<uuid:scheduleId>/enabled/",
        views.change_schedule_enabled,
        name="schedule-enabled",
    ),
    path(
        "<uuid:scheduleId>/delete/",
        views.delete_schedule_record,
        name="schedule-delete",
    ),
]
