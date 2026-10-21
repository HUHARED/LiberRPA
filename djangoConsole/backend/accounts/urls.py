# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .account_deletion_views import get_or_delete_account
from .api_key_views import (
    edit_api_key_notes,
    list_or_create_api_keys,
    revoke_account_api_key,
)
from .email_change_views import (
    check_email_change_link,
    confirm_account_email_change,
    queue_email_change_verification,
)
from .editor_sessions import EditorClientAction
from .editor_views import sign_in_editor, process_editor_client_request
from .password_reset_views import (
    check_password_reset_link,
    queue_password_reset_email,
    reset_account_password,
)
from .password_views import change_account_password
from .profile_views import get_or_update_profile, update_platform_time_zone
from .public_api_views import get_api_key_access
from .session_views import (
    sign_in,
    sign_in_platform,
    get_current_session,
    get_current_access,
    sign_out,
    sign_out_other_sessions,
)
from .views import (
    get_csrf_token,
    queue_registration_email,
    check_registration_link,
    complete_registration,
)

urlpatterns = [
    path("clients/editor/login/", sign_in_editor, name="editor-client-login"),
    path(
        "clients/editor/session/",
        process_editor_client_request,
        {"action": EditorClientAction.SESSION},
        name="editor-client-session",
    ),
    path(
        "clients/editor/logout/",
        process_editor_client_request,
        {"action": EditorClientAction.LOGOUT},
        name="editor-client-logout",
    ),
    path("v1/access/", get_api_key_access, name="api-v1-access"),
    path("auth/csrf/", get_csrf_token, name="auth-csrf"),
    path("auth/login/", sign_in, name="auth-login"),
    path("platform/auth/login/", sign_in_platform, name="platform-auth-login"),
    path("auth/session/", get_current_session, name="auth-session"),
    path("auth/access/", get_current_access, name="auth-access"),
    path("auth/profile/", get_or_update_profile, name="auth-profile"),
    path(
        "platform/auth/time-zone/",
        update_platform_time_zone,
        name="platform-time-zone",
    ),
    path("auth/api-keys/", list_or_create_api_keys, name="auth-api-keys"),
    path(
        "auth/api-keys/<uuid:apiKeyId>/",
        edit_api_key_notes,
        name="auth-api-key-notes",
    ),
    path(
        "auth/api-keys/<uuid:apiKeyId>/revoke/",
        revoke_account_api_key,
        name="auth-api-key-revoke",
    ),
    path(
        "auth/account/deletion/",
        get_or_delete_account,
        name="auth-account-deletion",
    ),
    path(
        "auth/email/change/email/",
        queue_email_change_verification,
        name="email-change-email",
    ),
    path(
        "auth/email/change/check/",
        check_email_change_link,
        name="email-change-check",
    ),
    path(
        "auth/email/change/confirm/",
        confirm_account_email_change,
        name="email-change-confirm",
    ),
    path(
        "auth/password/change/",
        change_account_password,
        name="auth-password-change",
    ),
    path(
        "auth/password/reset/email/",
        queue_password_reset_email,
        name="password-reset-email",
    ),
    path(
        "auth/password/reset/check/",
        check_password_reset_link,
        name="password-reset-check",
    ),
    path(
        "auth/password/reset/complete/",
        reset_account_password,
        name="password-reset-complete",
    ),
    path("auth/logout/", sign_out, name="auth-logout"),
    path(
        "auth/sessions/logout-others/",
        sign_out_other_sessions,
        name="auth-logout-others",
    ),
    path(
        "auth/registration/email/",
        queue_registration_email,
        name="registration-email",
    ),
    path(
        "auth/registration/check/",
        check_registration_link,
        name="registration-check",
    ),
    path(
        "auth/registration/complete/",
        complete_registration,
        name="registration-complete",
    ),
]
