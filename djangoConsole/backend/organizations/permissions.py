# FileName: permissions.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Q, QuerySet
from django.db.models.lookups import Exact

from accounts.models import User

from .models import Organization, Membership, Department, DepartmentRole


class AccessChannel(StrEnum):
    """Credential categories that affect the available role permissions."""

    SESSION = "session"
    API_KEY = "api_key"
    EDITOR = "editor"
    EXECUTOR = "executor"


@dataclass(frozen=True)
class OrganizationAccessContext:
    """Business access for one operation, never a cache across requests or commits."""

    actor: User
    organization: Organization
    isOrgAdmin: bool
    channel: AccessChannel

    @property
    def actorId(self) -> uuid.UUID:
        return self.actor.pk


_DICT_ALLOWED_ROLE_BY_REQUIREMENT = {
    DepartmentRole.OPERATOR: (DepartmentRole.OPERATOR, DepartmentRole.DEVELOPER),
    DepartmentRole.DEVELOPER: (DepartmentRole.DEVELOPER,),
}


def is_organization_business_available(organization: Organization) -> bool:
    """Evaluate the already loaded organization for both status display and business guards."""
    # Deletion freezes business when requested, not when cleanup becomes due.
    return (
        organization.suspended_at is None and organization.deletion_requested_at is None
    )


def require_organization_business_available(organization: Organization) -> None:
    """Check the organization already loaded for the current operation without querying again."""
    if not is_organization_business_available(organization):
        raise PermissionDenied("Organization business operations are unavailable.")


def _get_active_memberships(actorId: uuid.UUID) -> QuerySet[Membership]:
    return Membership.objects.filter(user_id=actorId, user__is_active=True)


def get_current_membership(*, actorId: uuid.UUID) -> Membership:
    """Resolve current membership for identity and restricted organization status views.

    actorId comes from verified credentials; organization identity is resolved by the server.
    Business operations must still apply their service-state and action permission rules.
    """
    try:
        return (
            _get_active_memberships(actorId).select_related("organization", "user").get()
        )
    except Membership.DoesNotExist:
        raise PermissionDenied("Organization access is required.") from None


def _resolve_organization_member(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    forUpdate: bool,
) -> tuple[Organization, Membership]:
    """Load current identity facts; the caller applies the operation's service-state rule."""
    membershipQuery = _get_active_memberships(actorId).filter(
        organization_id=organizationId
    )
    try:
        if forUpdate:
            # Organization state changes and business writes take this lock first.
            organization = Organization.objects.select_for_update().get(pk=organizationId)
            # Keep the current membership and account stable through the write.
            membership = (
                membershipQuery
                .select_related("user")
                .select_for_update(of=("self", "user"))
                .get()
            )
        else:
            membership = membershipQuery.select_related("organization", "user").get()
            organization = cast(Organization, membership.organization)
    except (Organization.DoesNotExist, Membership.DoesNotExist):
        raise PermissionDenied("Organization access is required.") from None

    return organization, membership


def resolve_organization_access(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    forUpdate: bool = False,
) -> OrganizationAccessContext:
    """Resolve current organization business access after credential authentication.

    actorId and channel come from verified credentials, never from the request body.
    Restricted status viewing and deletion cancellation need separate authorization.
    forUpdate requires the caller's transaction and locks the organization before its member.
    The returned actor is the account loaded with the membership, locked for writes.
    Resolve again at a new operation or write boundary instead of reusing an old result.
    """
    if channel not in (
        AccessChannel.SESSION,
        AccessChannel.API_KEY,
        AccessChannel.EDITOR,
        AccessChannel.EXECUTOR,
    ):
        raise PermissionDenied("Unsupported access channel.")

    organization, membership = _resolve_organization_member(
        actorId=actorId, organizationId=organizationId, forUpdate=forUpdate
    )
    # Verify membership first so an outsider cannot discover the organization's state.
    require_organization_business_available(organization)
    return OrganizationAccessContext(
        actor=cast(User, membership.user),
        organization=organization,
        isOrgAdmin=membership.is_org_admin,
        channel=channel,
    )


def _require_organization_admin(isOrgAdmin: bool, channel: AccessChannel) -> None:
    if channel != AccessChannel.SESSION or not isOrgAdmin:
        raise PermissionDenied("Organization administrator access is required.")


def require_organization_admin(access: OrganizationAccessContext) -> None:
    """Require an administrator using a session credential."""
    _require_organization_admin(access.isOrgAdmin, access.channel)


def lock_organization_for_deletion(
    *, actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> tuple[Organization, User]:
    """Authorize deletion lifecycle operations without granting ordinary business access.

    The caller's transaction must contain the state transition and any password check.
    actorId and channel must come from verified credentials.
    """
    organization, membership = _resolve_organization_member(
        actorId=actorId, organizationId=organizationId, forUpdate=True
    )
    _require_organization_admin(membership.is_org_admin, channel)
    return organization, cast(User, membership.user)


def lock_account_for_password_reset(*, userId: uuid.UUID) -> tuple[Organization, User]:
    """Lock the current account for recovery without granting organization business access.

    The caller must verify the email proof before changing the password in this transaction.
    Recovery keeps login available for deletion cancellation; it never lifts a suspension.
    Return both locked records so a successful reset can record its audit without rereading identity.
    """
    currentMembership = get_current_membership(actorId=userId)
    organization, membership = _resolve_organization_member(
        actorId=userId,
        organizationId=currentMembership.organization_id,
        forUpdate=True,
    )
    return organization, cast(User, membership.user)


def has_other_active_organization_admin(
    *, organizationId: uuid.UUID, userId: uuid.UUID
) -> bool:
    """Check the administrator rule shared by demotion and account deletion.

    Writes must hold the organization lock before checking and changing membership.
    An active administrator counts even without a current login or department role.
    """
    return (
        Membership.objects
        .filter(organization_id=organizationId, is_org_admin=True, user__is_active=True)
        .exclude(user_id=userId)
        .exists()
    )


def get_department_access_query(
    *,
    actorId: uuid.UUID | OuterRef,
    organizationId: uuid.UUID,
    isOrgAdmin: bool | OuterRef,
    requiredRole: DepartmentRole,
) -> QuerySet[Department]:
    """Share department rules between verified access contexts and correlated session queries."""
    tupleAllowedRole = _DICT_ALLOWED_ROLE_BY_REQUIREMENT.get(requiredRole)
    if tupleAllowedRole is None:
        raise PermissionDenied("Unsupported department role requirement.")
    departmentQuery = Department.objects.filter(
        organization_id=organizationId, deleted_at__isnull=True
    )
    if isOrgAdmin is True:
        return departmentQuery

    # Match the actual department only; parent and sibling roles do not grant access.
    roleCondition = Q(
        memberships__membership_id=actorId,
        memberships__role__in=tupleAllowedRole,
    )
    if isinstance(isOrgAdmin, OuterRef):
        roleCondition |= Q(Exact(isOrgAdmin, True))
    return departmentQuery.filter(roleCondition)


def get_authorized_departments(
    access: OrganizationAccessContext, *, requiredRole: DepartmentRole
) -> QuerySet[Department]:
    """Return active departments that satisfy a server-selected role requirement.

    Reuse this queryset for filtering and object lookup within the current operation.
    A get() outside this scope raises Department.DoesNotExist.
    """
    departmentQuery = get_department_access_query(
        actorId=access.actorId,
        organizationId=access.organization.id,
        isOrgAdmin=access.isOrgAdmin,
        requiredRole=requiredRole,
    )
    if (
        access.channel == AccessChannel.API_KEY
        and requiredRole != DepartmentRole.OPERATOR
    ):
        raise PermissionDenied("API keys can only perform Operator actions.")
    return departmentQuery
