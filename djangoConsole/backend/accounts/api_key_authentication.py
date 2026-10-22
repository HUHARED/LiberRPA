# FileName: api_key_authentication.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    build_organization_access,
    resolve_organization_access,
)

from .models import ApiKey

_BEARER_PATTERN = re.compile(r"(?i:Bearer) +(lrpa_[A-Za-z0-9_-]{43})")


class InvalidApiKeyError(Exception):
    """The supplied credential cannot authenticate a current account."""


@dataclass(frozen=True)
class ApiKeyAuthenticationContext:
    """Verified identity for this read request; writes must revalidate under their own locks."""

    apiKeyId: uuid.UUID
    expiresAt: datetime
    access: OrganizationAccessContext


@sensitive_variables()
def authenticate_api_key(authorizationHeader: str) -> ApiKeyAuthenticationContext:
    """Verify a Bearer credential and resolve its owner's current organization access.

    This short transaction releases its key lock before the caller performs business work.
    Never call it while holding organization or account locks in an outer transaction.
    """
    credentialMatch = (
        _BEARER_PATTERN.fullmatch(authorizationHeader)
        if len(authorizationHeader) <= 128
        else None
    )
    if credentialMatch is None:
        raise InvalidApiKeyError("A valid API key is required.")
    strTokenHash = hashlib.sha256(credentialMatch.group(1).encode("ascii")).hexdigest()

    with transaction.atomic(durable=True):
        try:
            apiKey = (
                ApiKey.objects
                .select_for_update(of=("self",))
                .only("id", "user", "expires_at", "revoked_at", "last_used_at")
                .get(token_hash=strTokenHash)
            )
        except ApiKey.DoesNotExist:
            raise InvalidApiKeyError("A valid API key is required.") from None
        # Recheck after any wait for revocation, password changes, or another request.
        if apiKey.revoked_at is not None or apiKey.expires_at <= timezone.now():
            raise InvalidApiKeyError("A valid API key is required.")
        try:
            membership = get_current_membership(actorId=apiKey.user_id)
        except PermissionDenied:
            raise InvalidApiKeyError("A valid API key is required.") from None
        access = build_organization_access(membership, channel=AccessChannel.API_KEY)

        currentTime = timezone.now()
        if apiKey.expires_at <= currentTime:
            raise InvalidApiKeyError("A valid API key is required.")
        if apiKey.last_used_at is None or apiKey.last_used_at < currentTime:
            apiKey.last_used_at = currentTime
            apiKey.save(update_fields=["last_used_at"])

    # NOTE: Key expiry/revocation does not cancel accepted Jobs; execution checks current account permissions.
    return ApiKeyAuthenticationContext(
        apiKeyId=apiKey.pk, expiresAt=apiKey.expires_at, access=access
    )


def lock_api_key_write_access(
    authentication: ApiKeyAuthenticationContext,
) -> OrganizationAccessContext:
    """Revalidate identity and credential after waiting for the business write lock."""
    access = resolve_organization_access(
        actorId=authentication.access.actorId,
        organizationId=authentication.access.organization.pk,
        channel=AccessChannel.API_KEY,
        forUpdate=True,
    )
    apiKey = (
        ApiKey.objects
        .select_for_update()
        .filter(pk=authentication.apiKeyId, user_id=access.actorId)
        .first()
    )
    if (
        apiKey is None
        or apiKey.revoked_at is not None
        or apiKey.expires_at <= timezone.now()
    ):
        raise InvalidApiKeyError("A valid API key is required.")
    return access
