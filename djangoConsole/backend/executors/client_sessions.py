# FileName: client_sessions.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import re
import secrets
import uuid
from collections.abc import Generator
from contextlib import contextmanager
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
    RESOURCE = "resource"
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


@dataclass(frozen=True)
class ExecutorSessionIdentity:
    sessionId: uuid.UUID
    userId: uuid.UUID
    organizationId: uuid.UUID


@sensitive_variables()
def begin_executor_login(
    *, userId: uuid.UUID, verifiedAuthHash: str, computerName: str, clientVersion: str
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
        currentTime = timezone.now()
        from runs.services import update_jobs_for_revoked_sessions

        expiredSessions = ExecutorSession.objects.filter(
            organization=access.organization, expires_at__lte=currentTime
        )
        listExpiredSessionId = list(expiredSessions.values_list("id", flat=True))
        expiredSessions.delete()
        update_jobs_for_revoked_sessions(listExpiredSessionId)
        strToken = f"lrex_{secrets.token_urlsafe(32)}"
        session = ExecutorSession(
            user=user,
            organization=access.organization,
            token_hash=hashlib.sha256(strToken.encode("ascii")).hexdigest(),
            auth_hash=user.get_session_auth_hash(),
            computer_name=computerName.strip(),
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
def get_executor_session_identity(authorizationHeader: str) -> ExecutorSessionIdentity:
    """Resolve the credential once; permissions are checked inside each write transaction."""
    credentialMatch = (
        _CLIENT_BEARER_PATTERN.fullmatch(authorizationHeader)
        if len(authorizationHeader) <= 128
        else None
    )
    if credentialMatch is None:
        raise InvalidExecutorSessionError("A valid Executor session is required.")
    strTokenHash = hashlib.sha256(credentialMatch.group(1).encode("ascii")).hexdigest()
    try:
        session = ExecutorSession.objects.only("id", "user", "organization").get(
            token_hash=strTokenHash
        )
    except ExecutorSession.DoesNotExist:
        raise InvalidExecutorSessionError(
            "A valid Executor session is required."
        ) from None
    return ExecutorSessionIdentity(session.id, session.user_id, session.organization_id)


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


@contextmanager
@sensitive_variables()
def open_executor_client_request(
    *,
    identity: ExecutorSessionIdentity,
    action: ExecutorClientAction,
    executorId: uuid.UUID | None = None,
    pageNumber: int = 1,
    recordContact: bool = True,
) -> Generator[ExecutorClientResult | None]:
    """Keep one authenticated contact and its caller's writes in the same transaction.

    Call outside other transactions; the organization/account locks precede the session lock.
    The yielded access is valid only inside this context, not for later business transactions.
    """
    boolInvalidSession = False
    result: ExecutorClientResult | None = None
    with transaction.atomic(durable=True):
        if action == ExecutorClientAction.LOGOUT:
            # Ending only this credential remains available during an organization freeze.
            organization = (
                Organization.objects
                .select_for_update()
                .filter(pk=identity.organizationId)
                .first()
            )
            session = (
                ExecutorSession.objects
                .select_related("user")
                .filter(pk=identity.sessionId)
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
            from runs.services import update_jobs_for_revoked_sessions

            # The native client also guards actual local Runs before requesting logout.
            intDeletedCount, _ = ExecutorSession.objects.filter(
                pk=identity.sessionId
            ).delete()
            update_jobs_for_revoked_sessions([identity.sessionId])
            if not intDeletedCount:
                raise InvalidExecutorSessionError("A valid Executor session is required.")
            yield None
            return
        access = resolve_organization_access(
            actorId=identity.userId,
            organizationId=identity.organizationId,
            channel=AccessChannel.EXECUTOR,
            forUpdate=True,
        )
        try:
            session = get_locked_executor_session(access, identity.sessionId)
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
                        access,
                        pageNumber=pageNumber,
                        availableOnly=True,
                    )
                    # Listing choices never extends the ten-minute selection deadline.
                    result = ExecutorClientResult(
                        session=session, access=access, choices=choices
                    )
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
                        previousSession = (
                            get_executor_sessions(access.organization.id)
                            .filter(executor=executor)
                            .first()
                        )
                        if previousSession is not None:
                            if is_executor_session_current(
                                previousSession, currentTime=timezone.now()
                            ):
                                raise ValidationError(
                                    "This Executor already has a valid association.",
                                    code="executor_already_associated",
                                )
                            from runs.services import update_jobs_for_revoked_sessions

                            previousSessionId = previousSession.pk
                            previousSession.delete()
                            update_jobs_for_revoked_sessions([previousSessionId])
                        session.executor = executor
                        session.associated_at = max(timezone.now(), session.created_at)
                    # Repeating the same selection after a lost response preserves the original session.
                case (
                    ExecutorClientAction.SESSION
                    | ExecutorClientAction.HEARTBEAT
                    | ExecutorClientAction.RESOURCE
                ):
                    if session.executor_id is None:
                        raise ValidationError(
                            "Select an Executor to finish signing in.",
                            code="executor_selection_required",
                        )
                case _:
                    raise ValueError("Unsupported Executor client action.")

            if action != ExecutorClientAction.CHOICES:
                currentTime = timezone.now()
                # A wait or slow authorization must never renew a credential that has already expired.
                if session.expires_at <= currentTime:
                    raise InvalidExecutorSessionError(
                        "A valid Executor session is required."
                    )
                if recordContact:
                    session.expires_at = currentTime + _SESSION_IDLE_LIFETIME
                    listUpdateField = ["expires_at"]
                    if action != ExecutorClientAction.RESOURCE:
                        # Python resource traffic does not prove that the Executor is online.
                        session.last_seen_at = max(
                            currentTime, session.last_seen_at or session.created_at
                        )
                        listUpdateField.append("last_seen_at")
                    if boolNewAssociation:
                        listUpdateField.extend(["executor", "associated_at"])
                    session.save(update_fields=listUpdateField)

                    if boolNewAssociation:
                        record_audit(
                            "executor.associate",
                            actor=access.actor,
                            organization=access.organization,
                            target=session.executor,
                            channel=AuditChannel.EXECUTOR,
                        )
                result = ExecutorClientResult(session=session, access=access)
        except InvalidExecutorSessionError:
            from runs.services import update_jobs_for_revoked_sessions

            ExecutorSession.objects.filter(pk=identity.sessionId).delete()
            update_jobs_for_revoked_sessions([identity.sessionId])
            boolInvalidSession = True
        if result is not None:
            # Caller failures roll back contact writes; they do not invalidate a valid credential.
            yield result
    # Commit invalidation before reporting it; a later permission restoration cannot revive this login.
    if boolInvalidSession:
        raise InvalidExecutorSessionError("A valid Executor session is required.")
