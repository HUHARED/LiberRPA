# FileName: api_keys.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import cast

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, F, Q, QuerySet, When
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from organizations.models import Membership
from organizations.permissions import (
    AccessChannel,
    get_current_membership,
    require_organization_admin,
    resolve_organization_access,
)

from .models import ApiKey, ApiKeyStatus, User
from .session_revocation import SessionInvalidatedError


@dataclass(frozen=True)
class ApiKeyCreationResult:
    apiKey: ApiKey
    secret: str = field(repr=False)


def get_api_key_status(apiKey: ApiKey, *, currentTime: datetime) -> ApiKeyStatus:
    if apiKey.revoked_at is not None:
        return ApiKeyStatus.REVOKED
    if apiKey.expires_at <= currentTime:
        return ApiKeyStatus.EXPIRED
    return ApiKeyStatus.ACTIVE


def _get_management_owner(
    actorId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
    *,
    forUpdate: bool,
    asAdministrator: bool = False,
) -> Membership:
    """Authorize the actor before looking up another member or their key metadata."""
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to manage API keys.")
    membership = get_current_membership(actorId=actorId)
    access = resolve_organization_access(
        actorId=actorId,
        organizationId=membership.organization_id,
        channel=channel,
        forUpdate=forUpdate,
    )
    if asAdministrator or userId != actorId:
        require_organization_admin(access)
    membershipQuery = Membership.objects.filter(organization=access.organization)
    if forUpdate:
        membershipQuery = membershipQuery.select_related("user").select_for_update(
            of=("self", "user")
        )
    return membershipQuery.get(user_id=userId)


@sensitive_variables()
def _lock_management_owner(
    actorId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
    *,
    asAdministrator: bool = False,
) -> None:
    _get_management_owner(
        actorId, channel, userId, forUpdate=True, asAdministrator=asAdministrator
    )
    actor = User.objects.get(pk=actorId)
    # A request waiting behind password/session revocation must not issue a new credential.
    if (
        sessionExpiresAt <= timezone.now()
        or not sessionAuthHash
        or not constant_time_compare(sessionAuthHash, actor.get_session_auth_hash())
    ):
        raise SessionInvalidatedError("The current session is no longer valid.")


def _get_inactive_api_keys(userId: uuid.UUID, currentTime: datetime) -> QuerySet[ApiKey]:
    return (
        ApiKey.objects
        .filter(user_id=userId)
        .filter(Q(revoked_at__isnull=False) | Q(expires_at__lte=currentTime))
        .annotate(
            invalidatedAt=Case(
                When(revoked_at__isnull=False, then=F("revoked_at")),
                default=F("expires_at"),
            )
        )
    )


def _get_retained_inactive_ids(
    userId: uuid.UUID, currentTime: datetime, limits: LimitsConfig
) -> QuerySet[ApiKey, uuid.UUID]:
    retentionCutoff = currentTime - timedelta(days=limits.inactiveApiKeyRetentionDays)
    return (
        _get_inactive_api_keys(userId, currentTime)
        .filter(invalidatedAt__gt=retentionCutoff)
        .order_by("-invalidatedAt", "-created_at", "-id")
        .values_list("id", flat=True)[: limits.maxInactiveApiKeysPerAccount]
    )


def _get_retained_api_keys(userId: uuid.UUID, currentTime: datetime) -> QuerySet[ApiKey]:
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return ApiKey.objects.filter(user_id=userId).filter(
        Q(revoked_at__isnull=True, expires_at__gt=currentTime)
        | Q(pk__in=_get_retained_inactive_ids(userId, currentTime, limits))
    )


def _prune_inactive_api_keys(userId: uuid.UUID, currentTime: datetime) -> int:
    """Prune metadata while the caller holds the account lock; never delete active keys."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    retainedIds = _get_retained_inactive_ids(userId, currentTime, limits)
    _, dictDeletedCount = (
        _get_inactive_api_keys(userId, currentTime).exclude(pk__in=retainedIds).delete()
    )
    # Future business history must store its own identity facts, not cascade from a key.
    return dictDeletedCount.get(ApiKey._meta.label, 0)


def get_api_key_list(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
    statuses: tuple[ApiKeyStatus, ...] = (),
    asAdministrator: bool = False,
) -> tuple[ApiKey, ...]:
    """Read current owner/admin metadata; filtering happens after applying retention."""
    _get_management_owner(
        actorId, channel, userId, forUpdate=False, asAdministrator=asAdministrator
    )
    currentTime = timezone.now()
    apiKeys = (
        _get_retained_api_keys(userId, currentTime)
        .defer("token_hash")
        .order_by("-created_at", "-id")
    )
    return tuple(
        apiKey
        for apiKey in apiKeys
        if not statuses or get_api_key_status(apiKey, currentTime=currentTime) in statuses
    )


@sensitive_variables()
@transaction.atomic
def create_api_key(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    name: str,
    expiresAt: datetime,
    notes: str,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> ApiKeyCreationResult:
    """Issue a 256-bit secret for the authenticated owner, returning its plaintext once."""
    _lock_management_owner(actorId, channel, actorId, sessionAuthHash, sessionExpiresAt)
    currentTime = timezone.now()
    if timezone.is_naive(expiresAt) or expiresAt <= currentTime:
        raise ValidationError({"expires_at": "Choose a future time with a UTC offset."})
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    activeCount = ApiKey.objects.filter(
        user_id=actorId, revoked_at__isnull=True, expires_at__gt=currentTime
    ).count()
    if activeCount >= limits.maxActiveApiKeysPerAccount:
        raise ValidationError(
            "The active API key limit has been reached.", code="api_key_limit"
        )

    secretValue = f"lrpa_{secrets.token_urlsafe(32)}"
    apiKey = ApiKey(
        user_id=actorId,
        name=name.strip(),
        notes=notes,
        token_hash=hashlib.sha256(secretValue.encode("ascii")).hexdigest(),
        created_at=currentTime,
        expires_at=expiresAt,
    )
    apiKey.full_clean(validate_unique=False, validate_constraints=False)
    # Recheck after validation so an almost-expired request cannot create an expired key.
    if apiKey.expires_at <= timezone.now():
        raise ValidationError({"expires_at": "Choose a future expiry time."})
    apiKey.save(force_insert=True)
    _prune_inactive_api_keys(actorId, currentTime)
    return ApiKeyCreationResult(apiKey=apiKey, secret=secretValue)


@sensitive_variables()
@transaction.atomic
def update_api_key_notes(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    apiKeyId: uuid.UUID,
    notes: str,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> ApiKey:
    """Edit only the owner's Notes without changing credential state or retention."""
    _lock_management_owner(actorId, channel, actorId, sessionAuthHash, sessionExpiresAt)
    apiKey = _get_retained_api_keys(actorId, timezone.now()).get(pk=apiKeyId)
    apiKey.notes = notes
    apiKey.full_clean(validate_unique=False, validate_constraints=False)
    apiKey.save(update_fields=["notes"])
    return apiKey


@sensitive_variables()
@transaction.atomic
def revoke_api_key(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    userId: uuid.UUID,
    apiKeyId: uuid.UUID,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
    asAdministrator: bool = False,
) -> ApiKey:
    """Permanently revoke an active owner/member key; repeats preserve the first timestamp."""
    _lock_management_owner(
        actorId,
        channel,
        userId,
        sessionAuthHash,
        sessionExpiresAt,
        asAdministrator=asAdministrator,
    )
    currentTime = timezone.now()
    apiKey = _get_retained_api_keys(userId, currentTime).get(pk=apiKeyId)
    if apiKey.revoked_at is not None:
        return apiKey
    if apiKey.expires_at <= currentTime:
        raise ValidationError(
            "The API key has already expired.", code="api_key_not_active"
        )
    apiKey.revoked_at = currentTime
    apiKey.save(update_fields=["revoked_at"])
    _prune_inactive_api_keys(userId, currentTime)
    return apiKey


@transaction.atomic
def revoke_active_api_keys(*, userId: uuid.UUID) -> int:
    """Join the password-change/reset transaction and revoke only currently active keys."""
    User.objects.select_for_update().get(pk=userId)
    currentTime = timezone.now()
    revokedCount = ApiKey.objects.filter(
        user_id=userId, revoked_at__isnull=True, expires_at__gt=currentTime
    ).update(revoked_at=currentTime)
    _prune_inactive_api_keys(userId, currentTime)
    return revokedCount


def prune_inactive_api_keys() -> int:
    """Clean inactive metadata account by account, including accounts with no recent requests."""
    userIds = (
        ApiKey.objects
        .filter(Q(revoked_at__isnull=False) | Q(expires_at__lte=timezone.now()))
        .order_by("user_id")
        .values_list("user_id", flat=True)
        .distinct()
    )
    deletedCount = 0
    for userId in userIds.iterator(chunk_size=200):
        with transaction.atomic():
            if User.objects.select_for_update().filter(pk=userId).exists():
                deletedCount += _prune_inactive_api_keys(userId, timezone.now())
    return deletedCount
