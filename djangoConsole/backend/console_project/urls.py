# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from accounts.profile_views import get_or_update_profile
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
from organizations.department_views import (
    get_or_delete_department,
    get_or_update_department,
    list_or_create_departments,
)
from organizations.views import get_or_update_organization_settings

from .health import check_database, check_liveness

urlpatterns = [
    path("api/health/live/", check_liveness, name="health-live"),
    path("api/health/database/", check_database, name="health-database"),
    path("api/auth/csrf/", get_csrf_token, name="auth-csrf"),
    path("api/auth/login/", sign_in, name="auth-login"),
    path("api/auth/session/", get_current_session, name="auth-session"),
    path("api/auth/access/", get_current_access, name="auth-access"),
    path("api/auth/profile/", get_or_update_profile, name="auth-profile"),
    path("api/auth/logout/", sign_out, name="auth-logout"),
    path(
        "api/organization/settings/",
        get_or_update_organization_settings,
        name="organization-settings",
    ),
    path(
        "api/organization/departments/",
        list_or_create_departments,
        name="organization-departments",
    ),
    path(
        "api/organization/departments/<uuid:departmentId>/",
        get_or_update_department,
        name="organization-department",
    ),
    path(
        "api/organization/departments/<uuid:departmentId>/deletion/",
        get_or_delete_department,
        name="organization-department-deletion",
    ),
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
