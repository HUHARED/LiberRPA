# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from accounts.session_views import (
    get_current_access,
    get_current_session,
    sign_in,
    sign_out,
)
from accounts.views import (
    check_registration_link,
    complete_registration,
    get_csrf_token,
    queue_registration_email,
)

from .health import check_database, check_liveness

urlpatterns = [
    path("api/health/live/", check_liveness, name="health-live"),
    path("api/health/database/", check_database, name="health-database"),
    path("api/auth/csrf/", get_csrf_token, name="auth-csrf"),
    path("api/auth/login/", sign_in, name="auth-login"),
    path("api/auth/session/", get_current_session, name="auth-session"),
    path("api/auth/access/", get_current_access, name="auth-access"),
    path("api/auth/logout/", sign_out, name="auth-logout"),
    path(
        "api/auth/registration/email/",
        queue_registration_email,
        name="registration-email",
    ),
    path(
        "api/auth/registration/check/",
        check_registration_link,
        name="registration-check",
    ),
    path(
        "api/auth/registration/complete/",
        complete_registration,
        name="registration-complete",
    ),
]
