# FileName: session_revocation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime

from django.contrib.auth.hashers import check_password
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from executors.session_state import revoke_user_executor_sessions
from operations.contracts import AuditAction
from operations.audit import record_audit
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    resolve_organization_access,
)

from .models import User
from .editor_sessions import revoke_user_editor_sessions


class SessionInvalidatedError(PermissionDenied):
    """The initiating session became invalid before its operation obtained the account lock."""


@sensitive_variables()
def require_current_session(
    actor: User,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
    sessionKey: str | None,
) -> None:
    """Recheck the initiating browser session against the account already locked by the caller."""
    currentTime = timezone.now()
    if (
        sessionExpiresAt <= currentTime
        or not sessionAuthHash
        or not constant_time_compare(sessionAuthHash, actor.get_session_auth_hash())
        or not sessionKey
        or not Session.objects.filter(
            session_key=sessionKey, expire_date__gt=currentTime
        ).exists()
    ):
        raise SessionInvalidatedError("The current session is no longer valid.")


@sensitive_variables()
def lock_session_write_access(
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
    sessionKey: str | None,
) -> OrganizationAccessContext:
    """Resolve current access and recheck a browser session after acquiring write locks."""
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required for this operation.")
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel, forUpdate=True
    )
    require_current_session(access.actor, sessionAuthHash, sessionExpiresAt, sessionKey)
    return access


@sensitive_variables()
def revoke_other_sessions(
    *,
    access: OrganizationAccessContext,
    currentPassword: str,
) -> User:
    """Advance the account's session version after verifying the initiating session.

    The caller supplies rechecked access and saves the kept session's new hash in the same transaction.
    """
    if access.channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to revoke sessions.")

    user = access.actor
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
    revoke_user_editor_sessions(user.id)
    record_audit(
        AuditAction.ACCOUNT_REVOKE_SESSIONS,
        actor=user,
        organization=access.organization,
        target=user,
        channel=access.channel,
    )
    # NOTE: Independent API keys and email-change proofs must not depend on this version.
    return user
