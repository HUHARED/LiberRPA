# FileName: rate_limits.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import math
from datetime import timedelta
from ipaddress import IPv6Address, ip_address
from typing import cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig

from .models import AuthenticationRequestLimit

_INT_PRUNE_BATCH_SIZE = 100


@transaction.atomic
def _prune_expired_request_limits() -> None:
    # Cleanup locks are released before taking the current counter's lock.
    # Skip active transactions and keep the work bounded for each request.
    listExpiredSourceHash = list(
        AuthenticationRequestLimit.objects
        .select_for_update(skip_locked=True)
        .filter(expires_at__lte=timezone.now())
        .order_by("expires_at", "source_hash")
        .values_list("source_hash", flat=True)[:_INT_PRUNE_BATCH_SIZE]
    )
    if listExpiredSourceHash:
        AuthenticationRequestLimit.objects.filter(
            source_hash__in=listExpiredSourceHash
        ).delete()


@sensitive_variables()
def _hash_client_address(clientAddress: str, *, scope: str) -> str:
    try:
        sourceAddress = ip_address(clientAddress)
    except ValueError:
        raise ImproperlyConfigured(
            "The HTTP server must supply a valid client IP address."
        ) from None
    if isinstance(sourceAddress, IPv6Address) and sourceAddress.ipv4_mapped is not None:
        sourceAddress = sourceAddress.ipv4_mapped
    return salted_hmac(scope, str(sourceAddress), algorithm="sha256").hexdigest()


def _reserve_request(sourceHash: str, *, maxRequests: int, windowSeconds: int) -> int:
    requestWindow = timedelta(seconds=windowSeconds)
    # Commit each counter before business work; failures do not refund attempts.
    with transaction.atomic(durable=True):
        requestLimit, _created = (
            AuthenticationRequestLimit.objects.select_for_update().get_or_create(
                source_hash=sourceHash,
                defaults={"expires_at": timezone.now() + requestWindow},
            )
        )
        # Recheck time after any wait for another request using the same counter.
        currentTime = timezone.now()
        windowExpired = requestLimit.expires_at <= currentTime
        if windowExpired:
            requestLimit.request_count = 0
            requestLimit.expires_at = currentTime + requestWindow

        if requestLimit.request_count >= maxRequests:
            if windowExpired:
                requestLimit.save(update_fields=["request_count", "expires_at"])
            return max(
                1, math.ceil((requestLimit.expires_at - currentTime).total_seconds())
            )

        requestLimit.request_count += 1
        requestLimit.save(update_fields=["request_count", "expires_at"])
    return 0


@sensitive_variables()
def reserve_registration_email_request(clientAddress: str) -> int:
    """Count an HTTP request, returning zero when allowed or a Retry-After in seconds.

    The caller supplies the server's client address, never an untrusted HTTP header.
    The counter commits before the email service runs, including for suppressed requests.
    """
    sourceHash = _hash_client_address(
        clientAddress, scope="accounts.registration_email.source"
    )
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_request_limits()
    return _reserve_request(
        sourceHash,
        maxRequests=limits.registrationEmailRequestsPerSource,
        windowSeconds=limits.registrationEmailRequestWindowSeconds,
    )


@sensitive_variables()
def reserve_registration_token_request(clientAddress: str, *, token: str) -> int:
    """Limit link reads and registration submissions by both source IP and email proof."""
    sourceHash = _hash_client_address(
        clientAddress, scope="accounts.registration_token.source"
    )
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_request_limits()
    retryAfterSeconds = _reserve_request(
        sourceHash,
        maxRequests=limits.registrationTokenRequestsPerSource,
        windowSeconds=limits.registrationTokenRequestWindowSeconds,
    )
    if retryAfterSeconds:
        return retryAfterSeconds

    # A source already over its limit cannot create more token counters.
    tokenHash = salted_hmac(
        "accounts.registration_token.proof", token, algorithm="sha256"
    ).hexdigest()
    return _reserve_request(
        tokenHash,
        maxRequests=limits.registrationTokenRequestsPerToken,
        windowSeconds=limits.registrationTokenRequestWindowSeconds,
    )


@sensitive_variables()
def reserve_login_request(clientAddress: str, *, normalizedEmail: str) -> int:
    """Count login attempts before password hashing, including unknown accounts.

    The caller supplies the canonical email and the HTTP server's actual client address.
    Limits are independent from registration and are not reset by successful login.
    """
    sourceHash = _hash_client_address(clientAddress, scope="accounts.login.source")
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_request_limits()
    retryAfterSeconds = _reserve_request(
        sourceHash,
        maxRequests=limits.loginRequestsPerSource,
        windowSeconds=limits.loginRequestWindowSeconds,
    )
    if retryAfterSeconds:
        return retryAfterSeconds

    accountHash = salted_hmac(
        "accounts.login.account", normalizedEmail, algorithm="sha256"
    ).hexdigest()
    return _reserve_request(
        accountHash,
        maxRequests=limits.loginRequestsPerAccount,
        windowSeconds=limits.loginRequestWindowSeconds,
    )


@sensitive_variables()
def reserve_password_change_request(clientAddress: str, *, actorId: str) -> int:
    """Limit signed-in password changes by source IP and the authenticated account ID.

    Counters commit before credential checks and remain independent of login requests.
    """
    sourceHash = _hash_client_address(
        clientAddress, scope="accounts.password_change.source"
    )
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_request_limits()
    retryAfterSeconds = _reserve_request(
        sourceHash,
        maxRequests=limits.passwordChangeRequestsPerSource,
        windowSeconds=limits.passwordChangeRequestWindowSeconds,
    )
    if retryAfterSeconds:
        return retryAfterSeconds

    accountHash = salted_hmac(
        "accounts.password_change.actor", actorId, algorithm="sha256"
    ).hexdigest()
    return _reserve_request(
        accountHash,
        maxRequests=limits.passwordChangeRequestsPerAccount,
        windowSeconds=limits.passwordChangeRequestWindowSeconds,
    )


@sensitive_variables()
def reserve_session_revocation_request(clientAddress: str, *, actorId: str) -> int:
    """Limit requests to sign out other sessions independently from login and password changes."""
    sourceHash = _hash_client_address(
        clientAddress, scope="accounts.session_revocation.source"
    )
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_request_limits()
    retryAfterSeconds = _reserve_request(
        sourceHash,
        maxRequests=limits.sessionRevocationRequestsPerSource,
        windowSeconds=limits.sessionRevocationRequestWindowSeconds,
    )
    if retryAfterSeconds:
        return retryAfterSeconds

    accountHash = salted_hmac(
        "accounts.session_revocation.actor", actorId, algorithm="sha256"
    ).hexdigest()
    return _reserve_request(
        accountHash,
        maxRequests=limits.sessionRevocationRequestsPerAccount,
        windowSeconds=limits.sessionRevocationRequestWindowSeconds,
    )


@sensitive_variables()
def reserve_invitation_email_request(clientAddress: str, *, actorId: str) -> int:
    """Limit administrator invitation requests independently from public registration."""
    sourceHash = _hash_client_address(
        clientAddress, scope="accounts.invitation_email.source"
    )
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_request_limits()
    retryAfterSeconds = _reserve_request(
        sourceHash,
        maxRequests=limits.invitationEmailRequestsPerSource,
        windowSeconds=limits.invitationEmailRequestWindowSeconds,
    )
    if retryAfterSeconds:
        return retryAfterSeconds
    accountHash = salted_hmac(
        "accounts.invitation_email.actor", actorId, algorithm="sha256"
    ).hexdigest()
    return _reserve_request(
        accountHash,
        maxRequests=limits.invitationEmailRequestsPerAccount,
        windowSeconds=limits.invitationEmailRequestWindowSeconds,
    )
