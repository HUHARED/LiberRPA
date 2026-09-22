# FileName: password_changes.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from executors.session_state import revoke_user_executor_sessions
from organizations.permissions import (
    AccessChannel,
    get_current_membership,
    resolve_organization_access,
)

from .api_keys import revoke_active_api_keys
from .models import User
from .passwords import validate_new_password


@sensitive_variables()
@transaction.atomic
def change_password(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    currentPassword: str,
    newPassword: str,
) -> None:
    """Change the signed-in account's password after checking its current credentials.

    actorId and channel come from verified credentials, never from the request body.
    Password changes use the same organization-first locks as other account writes.
    """
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to change the password.")

    membership = get_current_membership(actorId=actorId)
    resolve_organization_access(
        actorId=actorId,
        organizationId=membership.organization_id,
        channel=channel,
        forUpdate=True,
    )
    # The authorization service already locked this account; reload its current password hash.
    user = User.objects.get(pk=actorId)
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
    # NOTE: Email-change proofs are bound to the old password hash and are now invalid.
    # TODO: Revoke Editor credentials when Editor authentication is implemented.
