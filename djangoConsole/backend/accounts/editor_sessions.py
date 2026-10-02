# FileName: editor_sessions.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from operations.audit import record_audit
from operations.models import AuditChannel
from organizations.models import Organization
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    resolve_organization_access,
)

from .models import EditorSession

_SESSION_IDLE_LIFETIME = timedelta(days=14)
_EDITOR_BEARER_PATTERN = re.compile(r"(?i:Bearer) +(lred_[A-Za-z0-9_-]{43})")


class InvalidEditorSessionError(Exception):
    """The credential no longer authorizes this Editor login."""


class EditorClientAction(StrEnum):
    SESSION = "session"
    # Editor dosn't need to be managed by Console, so Heartbeat is unnecessary.
    # HEARTBEAT = "heartbeat"
    LOGOUT = "logout"


@dataclass(frozen=True)
class EditorClientResult:
    session: EditorSession
    access: OrganizationAccessContext
    token: str | None = field(default=None, repr=False)


def revoke_user_editor_sessions(userId: uuid.UUID) -> None:
    """Revoke Editor logins within the caller's account-security transaction."""
    EditorSession.objects.filter(user_id=userId).delete()


@sensitive_variables()
def begin_editor_login(
    *, userId: uuid.UUID, verifiedAuthHash: str, computer: str, clientVersion: str
) -> EditorClientResult:
    """Create an independent Editor credential after Django verifies the password."""
    with transaction.atomic(durable=True):
        membership = get_current_membership(actorId=userId)
        access = resolve_organization_access(
            actorId=userId,
            organizationId=membership.organization_id,
            channel=AccessChannel.EDITOR,
            forUpdate=True,
        )
        user = access.actor
        if not constant_time_compare(verifiedAuthHash, user.get_session_auth_hash()):
            raise InvalidEditorSessionError("Sign in again to continue.")
        currentTime = timezone.now()
        EditorSession.objects.filter(
            organization=access.organization, expires_at__lte=currentTime
        ).delete()
        strToken = f"lred_{secrets.token_urlsafe(32)}"
        session = EditorSession(
            user=user,
            organization=access.organization,
            token_hash=hashlib.sha256(strToken.encode("ascii")).hexdigest(),
            auth_hash=user.get_session_auth_hash(),
            computer=computer.strip(),
            client_version=clientVersion.strip(),
            created_at=currentTime,
            last_seen_at=currentTime,
            expires_at=currentTime + _SESSION_IDLE_LIFETIME,
        )
        session.full_clean()
        session.save(force_insert=True)
        record_audit(
            "editor_session.login",
            actor=user,
            organization=access.organization,
            target=session,
            channel=AuditChannel.EDITOR,
        )
    return EditorClientResult(session=session, access=access, token=strToken)


@sensitive_variables()
def _get_session_identity(authorizationHeader: str) -> EditorSession:
    credentialMatch = (
        _EDITOR_BEARER_PATTERN.fullmatch(authorizationHeader)
        if len(authorizationHeader) <= 128
        else None
    )
    if credentialMatch is None:
        raise InvalidEditorSessionError("A valid Editor session is required.")
    strTokenHash = hashlib.sha256(credentialMatch.group(1).encode("ascii")).hexdigest()
    try:
        return EditorSession.objects.only("id", "user", "organization").get(
            token_hash=strTokenHash
        )
    except EditorSession.DoesNotExist:
        raise InvalidEditorSessionError("A valid Editor session is required.") from None


@sensitive_variables()
def handle_editor_client_request(
    *, authorizationHeader: str, action: EditorClientAction
) -> EditorClientResult | None:
    """Recheck identity before renewal, using the shared organization/account lock order."""
    identity = _get_session_identity(authorizationHeader)
    boolInvalidSession = False
    result: EditorClientResult | None = None
    with transaction.atomic(durable=True):
        if action == EditorClientAction.LOGOUT:
            # Ending this credential remains available while organization business is frozen.
            organization = (
                Organization.objects
                .select_for_update()
                .filter(pk=identity.organization_id)
                .first()
            )
            session = (
                EditorSession.objects
                .select_related("user")
                .filter(pk=identity.id)
                .first()
            )
            if organization is None or session is None:
                raise InvalidEditorSessionError("A valid Editor session is required.")
            record_audit(
                "editor_session.logout",
                actor=session.user,
                organization=organization,
                target=session,
                channel=AuditChannel.EDITOR,
                before={},
            )
            session.delete()
            return None

        access = resolve_organization_access(
            actorId=identity.user_id,
            organizationId=identity.organization_id,
            channel=AccessChannel.EDITOR,
            forUpdate=True,
        )
        session = EditorSession.objects.select_for_update().filter(pk=identity.id).first()
        currentTime = timezone.now()
        if (
            session is None
            or session.expires_at <= currentTime
            or not constant_time_compare(
                session.auth_hash, access.actor.get_session_auth_hash()
            )
        ):
            EditorSession.objects.filter(pk=identity.id).delete()
            boolInvalidSession = True
        else:
            session.user = access.actor
            session.last_seen_at = max(currentTime, session.last_seen_at)
            session.expires_at = session.last_seen_at + _SESSION_IDLE_LIFETIME
            session.save(update_fields=["last_seen_at", "expires_at"])
            result = EditorClientResult(session=session, access=access)
    # Commit invalidation before rejecting the credential; it must never be renewed later.
    if boolInvalidSession:
        raise InvalidEditorSessionError("A valid Editor session is required.")
    return result
