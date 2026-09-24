# FileName: session_revocation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.contrib.auth.hashers import check_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from executors.session_state import revoke_user_executor_sessions
from operations.audit import record_audit
from organizations.permissions import (
    AccessChannel,
    get_current_membership,
    resolve_organization_access,
)

from .models import User


class SessionInvalidatedError(PermissionDenied):
    """The initiating session became invalid before its operation obtained the account lock."""


@sensitive_variables()
@transaction.atomic
def revoke_other_sessions(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    currentPassword: str,
    sessionAuthHash: str,
) -> User:
    """Advance the account's session version after verifying the initiating session.

    actorId, channel, and sessionAuthHash come from verified server-side authentication.
    The caller must save the kept session's new hash in the same outer transaction.
    """
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to revoke sessions.")

    membership = get_current_membership(actorId=actorId)
    resolve_organization_access(
        actorId=actorId,
        organizationId=membership.organization_id,
        channel=channel,
        forUpdate=True,
    )
    user = User.objects.get(pk=actorId)
    # NOTE: A request authenticated before a concurrent revocation must not revive its old session.
    if not sessionAuthHash or not constant_time_compare(
        sessionAuthHash, user.get_session_auth_hash()
    ):
        raise SessionInvalidatedError("The current session is no longer valid.")
    # Verify without a hash-upgrade setter; this action must leave password-based proofs valid.
    if not check_password(currentPassword, user.password):
        raise ValidationError({
            "current_password": ValidationError(
                "The current password is incorrect.", code="incorrect_password"
            )
        })

    user.session_version += 1
    user.save(update_fields=["session_version"])
    revoke_user_executor_sessions(user.id)
    record_audit("account.revoke_sessions", actorId=actorId, target=user, channel=channel)
    # NOTE: Independent API keys and email-change proofs must not depend on this version.
    # TODO: Revoke Editor credentials when Editor authentication is implemented.
    return user
