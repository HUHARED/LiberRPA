# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from accounts.views import get_csrf_token, send_registration_email

from .health import check_database, check_liveness

urlpatterns = [
    path("api/health/live/", check_liveness, name="health-live"),
    path("api/health/database/", check_database, name="health-database"),
    path("api/auth/csrf/", get_csrf_token, name="auth-csrf"),
    path(
        "api/auth/registration/email/",
        send_registration_email,
        name="registration-email",
    ),
]
