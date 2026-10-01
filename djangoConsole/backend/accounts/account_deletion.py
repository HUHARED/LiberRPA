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
from django.db import transaction
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from operations.audit import record_audit

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
from .session_revocation import SessionInvalidatedError


@dataclass(frozen=True)
class AccountDeletionInfo:
    userId: uuid.UUID
    email: str
    username: str
    isLastOrgAdmin: bool

    @property
    def canDelete(self) -> bool:
        return not self.isLastOrgAdmin


def _resolve_account_deletion_access(
    actorId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
    *,
    forUpdate: bool,
) -> tuple[OrganizationAccessContext, Membership]:
    """Resolve the actor's organization before looking up the target account."""
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to delete an account.")
    currentMembership = get_current_membership(actorId=actorId)
    access = resolve_organization_access(
        actorId=actorId,
        organizationId=currentMembership.organization_id,
        channel=channel,
        forUpdate=forUpdate,
    )
    if userId != actorId:
        require_organization_admin(access)

    membershipQuery = Membership.objects.select_related("user").filter(
        organization=access.organization
    )
    if forUpdate:
        membershipQuery = membershipQuery.select_for_update(of=("self", "user"))
    membership = membershipQuery.get(user_id=userId)
    return access, membership


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
    _, membership = _resolve_account_deletion_access(
        actorId, channel, userId, forUpdate=False
    )
    return _build_account_deletion_info(membership)


@sensitive_variables()
@transaction.atomic
def delete_account(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
    currentPassword: str,
    sessionAuthHash: str,
) -> None:
    """Delete the account after verifying current authority and the acting account's password.

    actorId, channel, and sessionAuthHash come from verified server-side authentication.
    The HTTP caller checks session expiry and logs out self-deletion in the same transaction.
    """
    access, membership = _resolve_account_deletion_access(
        actorId, channel, userId, forUpdate=True
    )
    actor = access.actor
    if not sessionAuthHash or not constant_time_compare(
        sessionAuthHash, actor.get_session_auth_hash()
    ):
        raise SessionInvalidatedError("The current session is no longer valid.")

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

    # Cascade membership, department roles, API keys, Executor sessions/associations, and private email proofs; retain organization resources and delivery history.
    target = cast(User, membership.user)
    record_audit(
        "account.delete",
        actor=actor,
        organization=access.organization,
        target=target,
        channel=channel,
    )
    target.delete()
    # Django rejects old web sessions because their User ID no longer resolves.
    # TODO: Revoke Editor credentials when Editor authentication is implemented.
