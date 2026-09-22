# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from accounts.account_deletion_views import get_or_delete_account
from accounts.email_change_views import (
    check_email_change_link,
    confirm_account_email_change,
    queue_email_change_verification,
)
from accounts.password_reset_views import (
    check_password_reset_link,
    queue_password_reset_email,
    reset_account_password,
)
from accounts.password_views import change_account_password
from accounts.profile_views import get_or_update_profile
from accounts.session_views import (
    get_current_access,
    get_current_session,
    sign_in,
    sign_out,
    sign_out_other_sessions,
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
from organizations.invitation_views import (
    check_invitation_link,
    complete_invited_registration,
    get_invitation_details,
    list_or_create_invitations,
    resend_or_revoke_invitation,
)
from organizations.member_views import get_or_update_member, list_members
from organizations.views import get_or_update_organization_settings

from .health import check_database, check_liveness

urlpatterns = [
    # Check application and database health.
    path("api/health/live/", check_liveness, name="health-live"),
    path("api/health/database/", check_database, name="health-database"),
    # Authenticate accounts and manage sessions, profiles, and registration.
    path("api/auth/csrf/", get_csrf_token, name="auth-csrf"),
    path("api/auth/login/", sign_in, name="auth-login"),
    path("api/auth/session/", get_current_session, name="auth-session"),
    path("api/auth/access/", get_current_access, name="auth-access"),
    path("api/auth/profile/", get_or_update_profile, name="auth-profile"),
    path(
        "api/auth/account/deletion/",
        get_or_delete_account,
        name="auth-account-deletion",
    ),
    path(
        "api/auth/email/change/email/",
        queue_email_change_verification,
        name="email-change-email",
    ),
    path(
        "api/auth/email/change/check/",
        check_email_change_link,
        name="email-change-check",
    ),
    path(
        "api/auth/email/change/confirm/",
        confirm_account_email_change,
        name="email-change-confirm",
    ),
    path(
        "api/auth/password/change/",
        change_account_password,
        name="auth-password-change",
    ),
    path(
        "api/auth/password/reset/email/",
        queue_password_reset_email,
        name="password-reset-email",
    ),
    path(
        "api/auth/password/reset/check/",
        check_password_reset_link,
        name="password-reset-check",
    ),
    path(
        "api/auth/password/reset/complete/",
        reset_account_password,
        name="password-reset-complete",
    ),
    path("api/auth/logout/", sign_out, name="auth-logout"),
    path(
        "api/auth/sessions/logout-others/",
        sign_out_other_sessions,
        name="auth-logout-others",
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
    path("api/auth/invitation/check/", check_invitation_link, name="invitation-check"),
    path(
        "api/auth/invitation/complete/",
        complete_invited_registration,
        name="invitation-complete",
    ),
    # Manage organization settings, departments, members, and invitations.
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
    path("api/organization/members/", list_members, name="organization-members"),
    path(
        "api/organization/members/<uuid:userId>/",
        get_or_update_member,
        name="organization-member",
    ),
    path(
        "api/organization/members/<uuid:userId>/deletion/",
        get_or_delete_account,
        name="organization-member-deletion",
    ),
    path(
        "api/organization/invitations/",
        list_or_create_invitations,
        name="organization-invitations",
    ),
    path(
        "api/organization/invitations/<uuid:invitationId>/",
        get_invitation_details,
        name="organization-invitation",
    ),
    path(
        "api/organization/invitations/<uuid:invitationId>/resend/",
        resend_or_revoke_invitation,
        {"resend": True},
        name="organization-invitation-resend",
    ),
    path(
        "api/organization/invitations/<uuid:invitationId>/revoke/",
        resend_or_revoke_invitation,
        {"resend": False},
        name="organization-invitation-revoke",
    ),
]
