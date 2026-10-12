# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from accounts.account_deletion_views import get_or_delete_account
from accounts.api_key_views import (
    list_or_create_api_keys,
    revoke_account_api_key,
)
from .department_views import (
    list_or_create_departments,
    get_or_update_department,
    get_or_delete_department,
)
from .invitation_views import (
    list_or_create_invitations,
    get_invitation_details,
    resend_or_revoke_invitation,
    check_invitation_link,
    complete_invited_registration,
)
from .lifecycle_views import (
    cancel_scheduled_organization_deletion,
    get_or_schedule_organization_deletion,
)
from .member_views import (
    get_or_update_member,
    list_members,
)
from .views import get_or_update_organization_settings

urlpatterns = [
    path("auth/invitation/check/", check_invitation_link, name="invitation-check"),
    path(
        "auth/invitation/complete/",
        complete_invited_registration,
        name="invitation-complete",
    ),
    path(
        "organization/settings/",
        get_or_update_organization_settings,
        name="organization-settings",
    ),
    path(
        "organization/deletion/",
        get_or_schedule_organization_deletion,
        name="organization-deletion",
    ),
    path(
        "organization/deletion/cancel/",
        cancel_scheduled_organization_deletion,
        name="organization-deletion-cancel",
    ),
    path(
        "organization/departments/",
        list_or_create_departments,
        name="organization-departments",
    ),
    path(
        "organization/departments/<uuid:departmentId>/",
        get_or_update_department,
        name="organization-department",
    ),
    path(
        "organization/departments/<uuid:departmentId>/deletion/",
        get_or_delete_department,
        name="organization-department-deletion",
    ),
    path("organization/members/", list_members, name="organization-members"),
    path(
        "organization/members/<uuid:userId>/",
        get_or_update_member,
        name="organization-member",
    ),
    path(
        "organization/members/<uuid:userId>/deletion/",
        get_or_delete_account,
        name="organization-member-deletion",
    ),
    path(
        "organization/members/<uuid:userId>/api-keys/",
        list_or_create_api_keys,
        name="organization-member-api-keys",
    ),
    path(
        "organization/members/<uuid:userId>/api-keys/<uuid:apiKeyId>/revoke/",
        revoke_account_api_key,
        name="organization-member-api-key-revoke",
    ),
    path(
        "organization/invitations/",
        list_or_create_invitations,
        name="organization-invitations",
    ),
    path(
        "organization/invitations/<uuid:invitationId>/",
        get_invitation_details,
        name="organization-invitation",
    ),
    path(
        "organization/invitations/<uuid:invitationId>/resend/",
        resend_or_revoke_invitation,
        {"resend": True},
        name="organization-invitation-resend",
    ),
    path(
        "organization/invitations/<uuid:invitationId>/revoke/",
        resend_or_revoke_invitation,
        {"resend": False},
        name="organization-invitation-revoke",
    ),
]
