# FileName: invitations.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import math
import re
import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from accounts.models import User, UserManager
from console_project.config import LimitsConfig
from notifications.models import EmailDelivery, EmailType
from operations.audit import get_audit_snapshot, record_audit

from .models import (
    Department,
    DepartmentMembership,
    DepartmentRole,
    InvitationDepartmentRole,
    InvitationStatus,
    MemberInvitation,
    Membership,
    Organization,
)
from .permissions import (
    AccessChannel,
    require_organization_business_available,
    lock_organization_admin_access,
)

_INVITATION_LIFETIME = timedelta(hours=12)
_INVITATION_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


class InvitationConflictError(Exception):
    def __init__(self, errorCode: str, message: str) -> None:
        self.errorCode = errorCode
        super().__init__(message)


class InvitationCooldownError(Exception):
    def __init__(self, retryAfterSeconds: int) -> None:
        self.retryAfterSeconds = retryAfterSeconds
        super().__init__("Wait before requesting another invitation email.")


@dataclass(frozen=True)
class InvitationDeliveryInfo:
    email: str
    organizationName: str
    token: str = field(repr=False)
    expiresAt: datetime


def get_pending_invitations(organizationId: uuid.UUID) -> QuerySet[MemberInvitation]:
    """Count reservations using current time; expiry needs no cleanup job."""
    return MemberInvitation.objects.filter(
        organization_id=organizationId,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    )


def get_invitation_status(invitation: MemberInvitation) -> InvitationStatus:
    if invitation.accepted_at is not None:
        return InvitationStatus.ACCEPTED
    if invitation.revoked_at is not None:
        return InvitationStatus.REVOKED
    return (
        InvitationStatus.PENDING
        if invitation.expires_at > timezone.now()
        else InvitationStatus.EXPIRED
    )


def _require_member_capacity(
    organizationId: uuid.UUID, *, invitationId: uuid.UUID | None = None
) -> None:
    # TODO: Apply organization-specific member limits when quota overrides are implemented.
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    pendingQuery = get_pending_invitations(organizationId)
    if invitationId is not None:
        pendingQuery = pendingQuery.exclude(pk=invitationId)
    # NOTE: Inactive members still count. Acceptance replaces its own reservation.
    intUsedCount = Membership.objects.filter(organization_id=organizationId).count()
    if intUsedCount + pendingQuery.count() >= limits.maxMembersPerOrganization:
        raise InvitationConflictError(
            "member_limit_reached", "The member limit has been reached."
        )


def _require_unregistered_email(email: str) -> None:
    if User.objects.filter(email=email).exists():
        raise InvitationConflictError(
            "email_already_registered", "This email address is already registered."
        )


def _validate_department_roles(
    organizationId: uuid.UUID, departmentRoles: Mapping[uuid.UUID, DepartmentRole]
) -> None:
    intDepartmentCount = Department.objects.filter(
        pk__in=departmentRoles, organization_id=organizationId, deleted_at__isnull=True
    ).count()
    if intDepartmentCount != len(departmentRoles) or any(
        role not in DepartmentRole.values for role in departmentRoles.values()
    ):
        raise ValidationError({
            "department_roles": "Select available departments and valid roles in this organization."
        })


def _get_invitation_roles(
    invitation: MemberInvitation,
) -> dict[uuid.UUID, DepartmentRole]:
    return {
        departmentId: DepartmentRole(role)
        for departmentId, role in InvitationDepartmentRole.objects.filter(
            invitation=invitation
        ).values_list("department_id", "role")
    }


def _require_recipient_cooldown(organizationId: uuid.UUID, email: str) -> None:
    previousInvitation = (
        MemberInvitation.objects
        .filter(organization_id=organizationId, email=email)
        .order_by("-requested_at", "-id")
        .first()
    )
    if previousInvitation is None:
        return
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    retryAt = previousInvitation.requested_at + timedelta(
        seconds=limits.emailResendSeconds
    )
    intRetrySeconds = math.ceil((retryAt - timezone.now()).total_seconds())
    if intRetrySeconds > 0:
        raise InvitationCooldownError(intRetrySeconds)


def _queue_invitation_email(invitation: MemberInvitation) -> None:
    # NOTE: Never lock old deliveries while holding the organization lock.
    # Workers lock delivery and dispatch before organization; stale requests are skipped.
    EmailDelivery.objects.create(
        email_type=EmailType.MEMBER_INVITATION,
        recipient=invitation.email,
        invitation=invitation,
        invitation_request_id=invitation.request_id,
    )


@transaction.atomic
def create_member_invitation(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    email: str,
    isOrgAdmin: bool,
    departmentRoles: Mapping[uuid.UUID, DepartmentRole],
    notes: str,
) -> MemberInvitation:
    access = lock_organization_admin_access(actorId, organizationId, channel)
    organization = access.organization
    requestedAt = timezone.now()
    invitation = MemberInvitation(
        organization=organization,
        email=UserManager.normalize_email(email),
        is_org_admin=isOrgAdmin,
        notes=notes,
        requested_at=requestedAt,
        expires_at=requestedAt + _INVITATION_LIFETIME,
    )
    invitation.full_clean(
        exclude=["token_hash"], validate_unique=False, validate_constraints=False
    )
    _validate_department_roles(organization.id, departmentRoles)
    _require_unregistered_email(invitation.email)
    if get_pending_invitations(organization.id).filter(email=invitation.email).exists():
        raise InvitationConflictError(
            "invitation_already_pending",
            "An invitation is already pending for this address.",
        )
    _require_recipient_cooldown(organization.id, invitation.email)
    _require_member_capacity(organization.id)
    invitation.save(force_insert=True)
    InvitationDepartmentRole.objects.bulk_create([
        InvitationDepartmentRole(
            invitation=invitation, department_id=departmentId, role=role
        )
        for departmentId, role in departmentRoles.items()
    ])
    _queue_invitation_email(invitation)
    record_audit(
        "invitation.create",
        actor=access.actor,
        organization=organization,
        target=invitation,
        channel=channel,
        before={},
    )
    return invitation


@transaction.atomic
def resend_member_invitation(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    invitationId: uuid.UUID,
) -> MemberInvitation:
    access = lock_organization_admin_access(actorId, organizationId, channel)
    organization = access.organization
    invitation = MemberInvitation.objects.select_for_update().get(
        pk=invitationId, organization=organization
    )
    if invitation.accepted_at is not None or invitation.revoked_at is not None:
        raise InvitationConflictError(
            "invitation_closed", "This invitation is already closed."
        )
    _require_unregistered_email(invitation.email)
    _validate_department_roles(organization.id, _get_invitation_roles(invitation))
    if (
        get_pending_invitations(organization.id)
        .filter(email=invitation.email)
        .exclude(pk=invitation.id)
        .exists()
    ):
        raise InvitationConflictError(
            "invitation_already_pending",
            "A newer invitation is already pending for this address.",
        )
    _require_recipient_cooldown(organization.id, invitation.email)
    _require_member_capacity(organization.id, invitationId=invitation.id)
    dictAuditBefore = get_audit_snapshot(invitation)
    invitation.requested_at = timezone.now()
    invitation.expires_at = invitation.requested_at + _INVITATION_LIFETIME
    invitation.request_id = uuid.uuid4()
    invitation.token_hash = None
    invitation.save(
        update_fields=["requested_at", "expires_at", "request_id", "token_hash"]
    )
    _queue_invitation_email(invitation)
    record_audit(
        "invitation.resend",
        actor=access.actor,
        organization=organization,
        target=invitation,
        channel=channel,
        before=dictAuditBefore,
    )
    return invitation


@transaction.atomic
def revoke_member_invitation(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    invitationId: uuid.UUID,
) -> MemberInvitation:
    access = lock_organization_admin_access(actorId, organizationId, channel)
    organization = access.organization
    invitation = MemberInvitation.objects.select_for_update().get(
        pk=invitationId, organization=organization
    )
    if invitation.accepted_at is not None:
        raise InvitationConflictError(
            "invitation_accepted", "An accepted invitation cannot remove its member."
        )
    if invitation.revoked_at is None:
        invitation.revoked_at = timezone.now()
        invitation.token_hash = None
        invitation.save(update_fields=["revoked_at", "token_hash"])
        record_audit(
            "invitation.revoke",
            actor=access.actor,
            organization=organization,
            target=invitation,
            channel=channel,
        )
    return invitation


def _require_invitation_pending(invitation: MemberInvitation) -> None:
    if get_invitation_status(invitation) != InvitationStatus.PENDING:
        raise ValidationError(
            "The invitation link is invalid or expired.", code="invalid_invitation_token"
        )


def _require_invitation_eligible(
    invitation: MemberInvitation, organization: Organization
) -> None:
    _require_invitation_pending(invitation)
    require_organization_business_available(organization)
    _require_unregistered_email(invitation.email)
    _validate_department_roles(organization.id, _get_invitation_roles(invitation))
    _require_member_capacity(organization.id, invitationId=invitation.id)


@sensitive_variables()
@transaction.atomic
def issue_invitation_token(delivery: EmailDelivery) -> InvitationDeliveryInfo | None:
    """Issue a private token only for the current request while the worker holds its delivery lock."""
    invitationReference = MemberInvitation.objects.get(pk=delivery.invitation_id)
    organization = Organization.objects.select_for_update().get(
        pk=invitationReference.organization_id
    )
    invitation = MemberInvitation.objects.select_for_update().get(
        pk=invitationReference.id
    )
    if (
        invitation.request_id != delivery.invitation_request_id
        or invitation.email != delivery.recipient
    ):
        return None
    _require_invitation_eligible(invitation, organization)
    strToken = secrets.token_urlsafe(32)
    invitation.token_hash = hashlib.sha256(strToken.encode("ascii")).hexdigest()
    invitation.save(update_fields=["token_hash"])
    return InvitationDeliveryInfo(
        email=invitation.email,
        organizationName=organization.name,
        token=strToken,
        expiresAt=invitation.expires_at,
    )


@sensitive_variables()
def _get_invitation_by_token(token: str) -> tuple[MemberInvitation, Organization]:
    if _INVITATION_TOKEN_PATTERN.fullmatch(token) is None:
        raise ValidationError(
            "The invitation link is invalid or expired.", code="invalid_invitation_token"
        )
    strTokenHash = hashlib.sha256(token.encode("ascii")).hexdigest()
    try:
        # NOTE: The first read discovers the lock key only. Recheck the digest after locking.
        organizationId = MemberInvitation.objects.values_list(
            "organization_id", flat=True
        ).get(token_hash=strTokenHash)
        organization = Organization.objects.select_for_update().get(pk=organizationId)
        invitation = MemberInvitation.objects.select_for_update().get(
            token_hash=strTokenHash, organization=organization
        )
    except (MemberInvitation.DoesNotExist, Organization.DoesNotExist):
        raise ValidationError(
            "The invitation link is invalid or expired.", code="invalid_invitation_token"
        ) from None
    _require_invitation_eligible(invitation, organization)
    return invitation, organization


@sensitive_variables()
@transaction.atomic
def get_invitation_registration_info(token: str) -> tuple[str, str]:
    """Validate a link without consuming it or exposing administrator-only notes."""
    invitation, organization = _get_invitation_by_token(token)
    return invitation.email, organization.name


@sensitive_variables()
@transaction.atomic
def complete_invitation_registration(
    *, token: str, password: str, username: str = ""
) -> None:
    invitation, organization = _get_invitation_by_token(token)
    if password is None:
        raise ValidationError({"password": "A password is required."})
    strDisplayName = (
        username
        if username and not username.isspace()
        else f"User {uuid.uuid4().hex[:8]}"
    )
    try:
        # A savepoint keeps a competing email claim from breaking the surrounding transaction.
        with transaction.atomic():
            user = cast(UserManager, User.objects).create_user(
                invitation.email,
                password,
                username=strDisplayName,
                timeZone=organization.default_time_zone,
            )
    except IntegrityError:
        _require_unregistered_email(invitation.email)
        raise
    membership = Membership.objects.create(
        user=user,
        organization=organization,
        is_org_admin=invitation.is_org_admin,
        notes=invitation.notes,
    )
    DepartmentMembership.objects.bulk_create([
        DepartmentMembership(membership=membership, department_id=departmentId, role=role)
        for departmentId, role in _get_invitation_roles(invitation).items()
    ])
    # NOTE: Password hashing can cross the expiry boundary; roll back every new record then.
    _require_invitation_pending(invitation)
    invitation.accepted_at = timezone.now()
    invitation.token_hash = None
    invitation.save(update_fields=["accepted_at", "token_hash"])
    record_audit(
        "invitation.accept",
        actor=user,
        organization=organization,
        target=invitation,
    )
