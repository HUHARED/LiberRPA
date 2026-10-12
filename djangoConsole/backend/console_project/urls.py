# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import include, path

from .health import check_database, check_liveness, get_client_info

urlpatterns = [
    path("api/clients/info/", get_client_info, name="client-info"),
    path("api/health/live/", check_liveness, name="health-live"),
    path("api/health/database/", check_database, name="health-database"),
    # Applications own their endpoints; existing route names stay unnamespaced.
    path("api/", include("accounts.urls")),
    path("api/", include("organizations.urls")),
    path("api/", include("executors.urls")),
    path("api/", include("assets.urls")),
    path("api/", include("data_queues.urls")),
    path("api/", include("shared_files.urls")),
    path("api/packages/", include("packages.urls")),
    path("api/clients/editor/packages/", include("packages.editor_urls")),
    path("api/clients/executor/packages/", include("packages.executor_urls")),
    path("api/schedules/", include("schedules.urls")),
    path("api/", include("runs.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/run-email-recipients/", include("notifications.recipient_urls")),
    path("api/", include("operations.urls")),
]
