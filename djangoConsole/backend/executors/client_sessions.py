# FileName: client_sessions.py
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
from typing import cast

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from operations.audit import record_audit
from operations.models import AuditChannel
from organizations.models import DepartmentRole, Organization
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    resolve_organization_access,
    get_authorized_departments,
)

from .models import Executor, ExecutorSession
from .queries import ExecutorPageInfo, get_executor_list
from .session_state import (
    get_executor_sessions,
    is_executor_session_current,
    prune_executor_sessions,
)

_SELECTION_LIFETIME = timedelta(minutes=10)
_SESSION_IDLE_LIFETIME = timedelta(days=14)
_CLIENT_BEARER_PATTERN = re.compile(r"(?i:Bearer) +(lrex_[A-Za-z0-9_-]{43})")


class InvalidExecutorSessionError(Exception):
    """The credential cannot continue this login or association."""


class ExecutorClientAction(StrEnum):
    CHOICES = "choices"
    ASSOCIATE = "associate"
    SESSION = "session"
    HEARTBEAT = "heartbeat"
    LOGOUT = "logout"


@dataclass(frozen=True)
class ExecutorLoginResult:
    session: ExecutorSession
    access: OrganizationAccessContext
    token: str = field(repr=False)


@dataclass(frozen=True)
class ExecutorClientResult:
    session: ExecutorSession
    access: OrganizationAccessContext
    choices: ExecutorPageInfo | None = None


@sensitive_variables()
def begin_executor_login(
    *, userId: uuid.UUID, verifiedAuthHash: str, computer: str, clientVersion: str
) -> ExecutorLoginResult:
    """Create a short selection-only credential after Django verifies the account password."""
    with transaction.atomic(durable=True):
        membership = get_current_membership(actorId=userId)
        access = resolve_organization_access(
            actorId=userId,
            organizationId=membership.organization_id,
            channel=AccessChannel.EXECUTOR,
            forUpdate=True,
        )
        user = access.actor
        if not constant_time_compare(verifiedAuthHash, user.get_session_auth_hash()):
            raise InvalidExecutorSessionError("Sign in again to continue.")
        prune_executor_sessions(access.organization.id)
        currentTime = timezone.now()
        strToken = f"lrex_{secrets.token_urlsafe(32)}"
        session = ExecutorSession(
            user=user,
            organization=access.organization,
            token_hash=hashlib.sha256(strToken.encode("ascii")).hexdigest(),
            auth_hash=user.get_session_auth_hash(),
            computer=computer.strip(),
            client_version=clientVersion.strip(),
            created_at=currentTime,
            expires_at=currentTime + _SELECTION_LIFETIME,
        )
        session.full_clean()
        session.save(force_insert=True)
        record_audit(
            "executor_session.login",
            actor=access.actor,
            organization=access.organization,
            target=session,
            channel=AuditChannel.EXECUTOR,
        )
    return ExecutorLoginResult(session=session, access=access, token=strToken)


@sensitive_variables()
def _get_session_identity(authorizationHeader: str) -> ExecutorSession:
    credentialMatch = (
        _CLIENT_BEARER_PATTERN.fullmatch(authorizationHeader)
        if len(authorizationHeader) <= 128
        else None
    )
    if credentialMatch is None:
        raise InvalidExecutorSessionError("A valid Executor session is required.")
    strTokenHash = hashlib.sha256(credentialMatch.group(1).encode("ascii")).hexdigest()
    try:
        return ExecutorSession.objects.only("id", "user", "organization").get(
            token_hash=strTokenHash
        )
    except ExecutorSession.DoesNotExist:
        raise InvalidExecutorSessionError(
            "A valid Executor session is required."
        ) from None


def _touch_executor_session(session: ExecutorSession) -> None:
    currentTime = timezone.now()
    # A wait or slow authorization must never renew a credential that has already expired.
    if session.expires_at <= currentTime:
        raise InvalidExecutorSessionError("A valid Executor session is required.")
    session.last_seen_at = max(currentTime, session.last_seen_at or session.created_at)
    session.expires_at = session.last_seen_at + _SESSION_IDLE_LIFETIME
    session.save(
        update_fields=["executor", "associated_at", "last_seen_at", "expires_at"]
    )


@sensitive_variables()
def get_locked_executor_session(
    access: OrganizationAccessContext, sessionId: uuid.UUID
) -> ExecutorSession:
    """Apply the same account and association rules after acquiring business locks."""
    try:
        session = (
            get_executor_sessions(access.organization.pk)
            .select_for_update(of=("self",))
            .get(pk=sessionId, user_id=access.actorId)
        )
    except ExecutorSession.DoesNotExist:
        raise InvalidExecutorSessionError(
            "A valid Executor session is required."
        ) from None
    if not is_executor_session_current(session, currentTime=timezone.now()):
        raise InvalidExecutorSessionError("A valid Executor session is required.")
    return session


def _perform_executor_action(
    session: ExecutorSession,
    access: OrganizationAccessContext,
    action: ExecutorClientAction,
    executorId: uuid.UUID | None,
    pageNumber: int,
) -> ExecutorClientResult:
    boolNewAssociation = (
        action == ExecutorClientAction.ASSOCIATE and session.executor_id is None
    )
    match action:
        case ExecutorClientAction.CHOICES:
            if session.executor_id is not None:
                raise ValidationError(
                    "Sign out before selecting another Executor.",
                    code="executor_already_associated",
                )
            choices = get_executor_list(
                actorId=session.user_id,
                organizationId=session.organization_id,
                channel=AccessChannel.EXECUTOR,
                pageNumber=pageNumber,
                availableOnly=True,
            )
            # Listing choices never extends the ten-minute selection deadline.
            return ExecutorClientResult(session=session, access=access, choices=choices)
        case ExecutorClientAction.ASSOCIATE:
            if session.executor_id is not None:
                if session.executor_id != executorId:
                    raise ValidationError(
                        "Sign out before selecting another Executor.",
                        code="executor_already_associated",
                    )
            else:
                executor = Executor.objects.select_related("department").get(
                    pk=executorId,
                    deleted_at__isnull=True,
                    department__in=get_authorized_departments(
                        access, requiredRole=DepartmentRole.OPERATOR
                    ),
                )
                prune_executor_sessions(access.organization.id)
                if ExecutorSession.objects.filter(executor=executor).exists():
                    raise ValidationError(
                        "This Executor already has a valid association.",
                        code="executor_already_associated",
                    )
                session.executor = executor
                session.associated_at = max(timezone.now(), session.created_at)
            # Repeating the same selection after a lost response preserves the original session.
        case ExecutorClientAction.SESSION | ExecutorClientAction.HEARTBEAT:
            if session.executor_id is None:
                raise ValidationError(
                    "Select an Executor to finish signing in.",
                    code="executor_selection_required",
                )
        case _:
            raise ValueError("Unsupported Executor client action.")

    _touch_executor_session(session)
    if boolNewAssociation:
        record_audit(
            "executor.associate",
            actor=access.actor,
            organization=access.organization,
            target=session.executor,
            channel=AuditChannel.EXECUTOR,
        )
    return ExecutorClientResult(session=session, access=access)


@sensitive_variables()
def handle_executor_client_request(
    *,
    authorizationHeader: str,
    action: ExecutorClientAction,
    executorId: uuid.UUID | None = None,
    pageNumber: int = 1,
) -> ExecutorClientResult | None:
    """Serialize authentication and state changes with account, membership, and Executor writes.

    Take the organization/account locks before the session lock, including for a heartbeat.
    Cookie sessions, API keys, and pending-selection credentials cannot substitute for an association.
    """
    identity = _get_session_identity(authorizationHeader)
    boolInvalidSession = False
    result: ExecutorClientResult | None = None
    with transaction.atomic(durable=True):
        if action == ExecutorClientAction.LOGOUT:
            # Ending only this credential remains available during an organization freeze.
            organization = (
                Organization.objects
                .select_for_update()
                .filter(pk=identity.organization_id)
                .first()
            )
            session = (
                ExecutorSession.objects
                .select_related("user")
                .filter(pk=identity.id)
                .first()
            )
            if organization is None or session is None:
                raise InvalidExecutorSessionError("A valid Executor session is required.")
            record_audit(
                "executor_session.logout",
                actor=cast(User, session.user),
                organization=organization,
                target=session,
                channel=AuditChannel.EXECUTOR,
                before={},
            )
            # TODO: The native client must block logout during any actual Run; add central-work checks with the Run model.
            intDeletedCount, _ = ExecutorSession.objects.filter(pk=identity.id).delete()
            if not intDeletedCount:
                raise InvalidExecutorSessionError("A valid Executor session is required.")
            return None
        access = resolve_organization_access(
            actorId=identity.user_id,
            organizationId=identity.organization_id,
            channel=AccessChannel.EXECUTOR,
            forUpdate=True,
        )
        try:
            session = get_locked_executor_session(access, identity.id)
            result = _perform_executor_action(
                session, access, action, executorId, pageNumber
            )
        except InvalidExecutorSessionError:
            ExecutorSession.objects.filter(pk=identity.id).delete()
            boolInvalidSession = True
    # Commit invalidation before reporting it; a later permission restoration cannot revive this login.
    if boolInvalidSession:
        raise InvalidExecutorSessionError("A valid Executor session is required.")
    return cast(ExecutorClientResult, result)
