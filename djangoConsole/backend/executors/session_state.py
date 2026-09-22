# FileName: session_state.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime
from typing import cast

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from organizations.models import DepartmentRole, Membership, Organization
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
)

from .models import Executor, ExecutorSession


def get_executor_sessions(organizationId: uuid.UUID) -> QuerySet[ExecutorSession]:
    return (
        ExecutorSession.objects
        .filter(organization_id=organizationId)
        .select_related("user__membership", "organization", "executor__department")
        .defer("token_hash")
    )


@sensitive_variables()
def is_executor_session_current(
    session: ExecutorSession, *, currentTime: datetime
) -> bool:
    """Check credential and resource eligibility without renewing it or treating Offline as expiry.

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
    access = OrganizationAccessContext(
        actorId=session.user_id,
        organization=cast(Organization, session.organization),
        isOrgAdmin=membership.is_org_admin,
        channel=AccessChannel.EXECUTOR,
    )
    return (
        get_authorized_departments(access, requiredRole=DepartmentRole.OPERATOR)
        .filter(pk=executor.department_id)
        .exists()
    )


def get_current_executor_sessions(
    organizationId: uuid.UUID, *, currentTime: datetime
) -> dict[uuid.UUID, ExecutorSession]:
    """Read current associations without changing their contact time or expiry."""
    return {
        cast(uuid.UUID, session.executor_id): session
        for session in get_executor_sessions(organizationId).filter(
            executor__isnull=False, expires_at__gt=currentTime
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
