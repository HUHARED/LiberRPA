# FileName: account_deletion.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from typing import cast

from django.contrib.auth.hashers import check_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.views.decorators.debug import sensitive_variables

from executors.session_state import revoke_user_executor_sessions
from operations.audit import record_audit
from runs.services import recheck_job_source_access

from organizations.models import Membership
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    resolve_organization_access,
    require_organization_admin,
    has_other_active_organization_admin,
)

from .models import User


@dataclass(frozen=True)
class AccountDeletionInfo:
    userId: uuid.UUID
    email: str
    username: str
    isLastOrgAdmin: bool

    @property
    def canDelete(self) -> bool:
        return not self.isLastOrgAdmin


def _get_account_deletion_membership(
    access: OrganizationAccessContext,
    userId: uuid.UUID,
    *,
    forUpdate: bool,
) -> Membership:
    """Use the current membership or find another member within the same organization."""
    if access.channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to delete an account.")
    if userId == access.actorId:
        return cast(Membership, getattr(access.actor, "membership"))  # noqa: B009
    require_organization_admin(access)

    membershipQuery = Membership.objects.select_related("user").filter(
        organization=access.organization
    )
    if forUpdate:
        membershipQuery = membershipQuery.select_for_update(of=("self", "user"))
    return membershipQuery.get(user_id=userId)


def _build_account_deletion_info(membership: Membership) -> AccountDeletionInfo:
    user = cast(User, membership.user)
    boolIsLastOrgAdmin = (
        membership.is_org_admin
        and user.is_active
        and not has_other_active_organization_admin(
            organizationId=membership.organization_id, userId=user.id
        )
    )
    return AccountDeletionInfo(
        userId=user.id,
        email=user.email,
        username=user.username,
        isLastOrgAdmin=boolIsLastOrgAdmin,
    )


def get_account_deletion_info(
    *, actorId: uuid.UUID, channel: AccessChannel, userId: uuid.UUID
) -> AccountDeletionInfo:
    """Preview account deletion without authorizing a later write or checking a password."""
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to delete an account.")
    currentMembership = get_current_membership(actorId=actorId)
    access = resolve_organization_access(
        actorId=actorId,
        organizationId=currentMembership.organization_id,
        channel=channel,
    )
    membership = _get_account_deletion_membership(access, userId, forUpdate=False)
    return _build_account_deletion_info(membership)


@sensitive_variables()
def delete_account(
    *,
    access: OrganizationAccessContext,
    userId: uuid.UUID,
    currentPassword: str,
) -> None:
    """Delete the account after verifying current authority and the acting account's password.

    The HTTP caller provides rechecked Session access and keeps deletion, the final expiry check, and self-deletion logout in the same transaction.
    """
    membership = _get_account_deletion_membership(access, userId, forUpdate=True)
    actor = access.actor

    # Verify without upgrading the actor's password hash or affecting their other sessions.
    if not check_password(currentPassword, actor.password):
        raise ValidationError({
            "current_password": ValidationError(
                "The current password is incorrect.", code="incorrect_password"
            )
        })

    if not _build_account_deletion_info(membership).canDelete:
        raise ValidationError(
            "The organization must retain at least one active administrator.",
            code="last_org_admin",
        )

    # Reconcile Executor associations before cascading account-owned credentials; retain resources and history.
    target = cast(User, membership.user)
    record_audit(
        "account.delete",
        actor=actor,
        organization=access.organization,
        target=target,
        channel=access.channel,
    )
    revoke_user_executor_sessions(userId)
    target.delete()
    recheck_job_source_access(userId, access.organization.id)
    # Django rejects old web sessions because their User ID no longer resolves.
