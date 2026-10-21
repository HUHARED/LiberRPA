# FileName: password_changes.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import PermissionDenied, ValidationError
from django.views.decorators.debug import sensitive_variables

from executors.session_state import revoke_user_executor_sessions
from operations.contracts import AuditAction
from operations.audit import record_audit
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
)

from .api_keys import revoke_active_api_keys
from .editor_sessions import revoke_user_editor_sessions
from .models import User
from .passwords import validate_new_password


@sensitive_variables()
def save_password_change(user: User) -> None:
    """Save the prepared password hash and revoke credentials in the caller's transaction."""
    # NOTE: Django rejects old web sessions when their stored authentication hash no longer matches.
    user.save(update_fields=["password"])
    revoke_active_api_keys(userId=user.id)
    revoke_user_executor_sessions(user.id)
    revoke_user_editor_sessions(user.id)
    # NOTE: Email-change and password-reset proofs are bound to the old password hash.


@sensitive_variables()
def change_password(
    *,
    access: OrganizationAccessContext,
    currentPassword: str,
    newPassword: str,
) -> None:
    """Change the password using rechecked session access in the caller's write transaction."""
    if access.channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to change the password.")

    user = access.actor
    if user.is_platform_admin:
        raise PermissionDenied("Reset the platform administrator password on the server.")
    if not user.check_password(currentPassword):
        raise ValidationError({
            "current_password": ValidationError(
                "The current password is incorrect.", code="incorrect_password"
            )
        })

    try:
        validate_new_password(newPassword, user)
    except ValidationError as e:
        raise ValidationError({"new_password": e.error_list}) from None

    user.set_password(newPassword)
    save_password_change(user)
    record_audit(
        AuditAction.ACCOUNT_CHANGE_PASSWORD,
        actor=user,
        organization=access.organization,
        target=user,
        channel=access.channel,
    )
