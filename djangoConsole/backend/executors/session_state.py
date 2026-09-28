# FileName: session_state.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Literal, cast

from django.conf import settings
from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from console_project.config import LimitsConfig
from organizations.models import DepartmentRole, Membership
from organizations.permissions import get_department_access_query

from .models import Executor, ExecutorSession


def get_executor_association_status(
    session: ExecutorSession | None, *, currentTime: datetime
) -> Literal["unassociated", "online", "offline"]:
    """Describe a session already checked for validity without changing its expiry."""
    if session is None:
        return "unassociated"
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    offlineAt = currentTime - timedelta(seconds=limits.executorOfflineSeconds)
    return (
        "online"
        if session.last_seen_at is not None and session.last_seen_at > offlineAt
        else "offline"
    )


def get_executor_sessions(organizationId: uuid.UUID) -> QuerySet[ExecutorSession]:
    """Load account facts and department authorization together for the current operation."""
    departmentQuery = get_department_access_query(
        actorId=OuterRef("user_id"),
        organizationId=organizationId,
        isOrgAdmin=OuterRef("user__membership__is_org_admin"),
        requiredRole=DepartmentRole.OPERATOR,
    )
    return (
        ExecutorSession.objects
        .filter(organization_id=organizationId)
        .annotate(
            can_use_department=Exists(
                departmentQuery.filter(pk=OuterRef("executor__department_id"))
            )
        )
        .select_related("user__membership", "executor")
        .defer("token_hash")
    )


@sensitive_variables()
def is_executor_session_current(
    session: ExecutorSession, *, currentTime: datetime
) -> bool:
    """Validate a session loaded by get_executor_sessions() for the current operation.

    Offline never means expired, and this check does not renew the session.
    Organization freezes are checked by every business entry point; they never renew a session.
    """
    user = cast(User, session.user)
    if (
        session.expires_at <= currentTime
        or not user.is_active
        or not constant_time_compare(session.auth_hash, user.get_session_auth_hash())
    ):
        return False
    membership = cast(Membership | None, getattr(user, "membership", None))
    if membership is None or membership.organization_id != session.organization_id:
        return False
    if session.executor_id is None:
        return True
    executor = cast(Executor, session.executor)
    if executor.deleted_at is not None:
        return False
    return session.can_use_department


def get_current_executor_sessions(
    organizationId: uuid.UUID,
    *,
    executorIds: Iterable[uuid.UUID],
    currentTime: datetime,
) -> dict[uuid.UUID, ExecutorSession]:
    """Read current associations only for the requested records, without renewing them."""
    return {
        cast(uuid.UUID, session.executor_id): session
        for session in get_executor_sessions(organizationId).filter(
            executor_id__in=executorIds, expires_at__gt=currentTime
        )
        if is_executor_session_current(session, currentTime=currentTime)
    }


def prune_executor_sessions(organizationId: uuid.UUID) -> int:
    """Remove unusable credentials while the caller holds the organization's write lock."""
    currentTime = timezone.now()
    invalidIds = [
        session.id
        for session in get_executor_sessions(organizationId)
        if not is_executor_session_current(session, currentTime=currentTime)
    ]
    count, _ = ExecutorSession.objects.filter(pk__in=invalidIds).delete()
    return count


def revoke_user_executor_sessions(userId: uuid.UUID) -> None:
    """Revoke pending logins and associations in the caller's account-security transaction."""
    ExecutorSession.objects.filter(user_id=userId).delete()
    # TODO: End undispatched direct work and preserve unresolved start facts when Jobs are implemented.


def revoke_unqualified_executor_sessions(
    userId: uuid.UUID, organizationId: uuid.UUID
) -> None:
    """Remove ineligible credentials within the membership update transaction."""
    currentTime = timezone.now()
    invalidIds = [
        session.id
        for session in get_executor_sessions(organizationId).filter(user_id=userId)
        if not is_executor_session_current(session, currentTime=currentTime)
    ]
    ExecutorSession.objects.filter(pk__in=invalidIds).delete()
