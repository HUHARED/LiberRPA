# FileName: password_changes.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import PermissionDenied, ValidationError
from django.views.decorators.debug import sensitive_variables

from executors.session_state import revoke_user_executor_sessions
from operations.audit import record_audit
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
)

from .api_keys import revoke_active_api_keys
from .editor_sessions import revoke_user_editor_sessions
from .passwords import validate_new_password


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
    # NOTE: Django rejects old web sessions when their stored authentication hash no longer matches.
    user.save(update_fields=["password"])
    revoke_active_api_keys(userId=user.id)
    revoke_user_executor_sessions(user.id)
    revoke_user_editor_sessions(user.id)
    record_audit(
        "account.change_password",
        actor=user,
        organization=access.organization,
        target=user,
        channel=access.channel,
    )
    # NOTE: Email-change proofs are bound to the old password hash and are now invalid.
