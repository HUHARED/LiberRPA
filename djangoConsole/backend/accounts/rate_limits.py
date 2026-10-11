# FileName: rate_limits.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import math
import time
from datetime import timedelta
from ipaddress import IPv6Address, ip_address
from threading import Lock
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
_INT_PRUNE_INTERVAL_SECONDS = 60
_LOCK_PRUNING = Lock()
_floatNextPruneAt = 0.0


def _delete_expired_request_counters_if_due() -> None:
    """Bound maintenance to one batch per minute per process, independently of request counts."""
    global _floatNextPruneAt

    floatCurrentTime = time.monotonic()
    if floatCurrentTime < _floatNextPruneAt or not _LOCK_PRUNING.acquire(blocking=False):
        return
    try:
        if floatCurrentTime < _floatNextPruneAt:
            return
        _floatNextPruneAt = floatCurrentTime + _INT_PRUNE_INTERVAL_SECONDS
        # Cleanup commits before the request's counter transaction and skips counters currently in use.
        with transaction.atomic():
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
    finally:
        _LOCK_PRUNING.release()


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


def _apply_request_rate_limit(
    sourceHash: str, *, maxRequests: int, windowSeconds: int
) -> int:
    requestWindow = timedelta(seconds=windowSeconds)
    # Commit each counter before business work; failures do not refund attempts.
    with transaction.atomic(durable=True):
        requestLimit, _ = (
            AuthenticationRequestLimit.objects.select_for_update().get_or_create(
                source_hash=sourceHash,
                defaults={"expires_at": timezone.now() + requestWindow},
            )
        )
        # Recheck time after any wait for another request using the same counter.
        currentTime = timezone.now()
        boolWindowExpired = requestLimit.expires_at <= currentTime
        if boolWindowExpired:
            requestLimit.request_count = 0
            requestLimit.expires_at = currentTime + requestWindow

        if requestLimit.request_count >= maxRequests:
            if boolWindowExpired:
                requestLimit.save(update_fields=["request_count", "expires_at"])
            return max(
                1, math.ceil((requestLimit.expires_at - currentTime).total_seconds())
            )

        requestLimit.request_count += 1
        requestLimit.save(update_fields=["request_count", "expires_at"])
    return 0


@sensitive_variables()
def _apply_source_rate_limit(
    clientAddress: str, *, scope: str, maxRequests: int, windowSeconds: int
) -> int:
    strSourceHash = _hash_client_address(clientAddress, scope=f"{scope}.source")
    _delete_expired_request_counters_if_due()
    return _apply_request_rate_limit(
        strSourceHash, maxRequests=maxRequests, windowSeconds=windowSeconds
    )


@sensitive_variables()
def _apply_source_and_subject_rate_limits(
    clientAddress: str,
    *,
    scope: str,
    subject: str,
    subjectKind: str,
    maxSourceRequests: int,
    maxSubjectRequests: int,
    windowSeconds: int,
) -> int:
    intRetryAfterSeconds = _apply_source_rate_limit(
        clientAddress,
        scope=scope,
        maxRequests=maxSourceRequests,
        windowSeconds=windowSeconds,
    )
    if intRetryAfterSeconds:
        return intRetryAfterSeconds

    # A blocked source cannot allocate additional account or proof counters.
    strSubjectHash = salted_hmac(
        f"{scope}.{subjectKind}", subject, algorithm="sha256"
    ).hexdigest()
    return _apply_request_rate_limit(
        strSubjectHash, maxRequests=maxSubjectRequests, windowSeconds=windowSeconds
    )


@sensitive_variables()
def _apply_sensitive_action_rate_limit(
    clientAddress: str, *, actorId: str, scope: str
) -> int:
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_and_subject_rate_limits(
        clientAddress,
        scope=scope,
        subject=actorId,
        subjectKind="actor",
        maxSourceRequests=limits.sensitiveActionRequestsPerSource,
        maxSubjectRequests=limits.sensitiveActionRequestsPerAccount,
        windowSeconds=limits.sensitiveActionRequestWindowSeconds,
    )


@sensitive_variables()
def _apply_email_token_rate_limit(clientAddress: str, *, token: str, scope: str) -> int:
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_and_subject_rate_limits(
        clientAddress,
        scope=scope,
        subject=token,
        subjectKind="proof",
        maxSourceRequests=limits.emailTokenRequestsPerSource,
        maxSubjectRequests=limits.emailTokenRequestsPerToken,
        windowSeconds=limits.emailTokenRequestWindowSeconds,
    )


@sensitive_variables()
def apply_registration_email_rate_limit(clientAddress: str) -> int:
    """Count an HTTP request, returning zero when allowed or a Retry-After in seconds.

    The caller supplies the server's client address, never an untrusted HTTP header.
    The counter commits before the email service runs, including for suppressed requests.
    """
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_rate_limit(
        clientAddress,
        scope="accounts.registration_email",
        maxRequests=limits.publicEmailRequestsPerSource,
        windowSeconds=limits.publicEmailRequestWindowSeconds,
    )


@sensitive_variables()
def apply_registration_token_rate_limit(clientAddress: str, *, token: str) -> int:
    """Limit link reads and registration submissions by both source IP and email proof."""
    return _apply_email_token_rate_limit(
        clientAddress, token=token, scope="accounts.registration_token"
    )


@sensitive_variables()
def apply_login_rate_limit(clientAddress: str, *, normalizedEmail: str) -> int:
    """Count login attempts before password hashing, including unknown accounts.

    The caller supplies the canonical email and the HTTP server's actual client address.
    Limits are independent from registration and are not reset by successful login.
    """
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_and_subject_rate_limits(
        clientAddress,
        scope="accounts.login",
        subject=normalizedEmail,
        subjectKind="account",
        maxSourceRequests=limits.loginRequestsPerSource,
        maxSubjectRequests=limits.loginRequestsPerAccount,
        windowSeconds=limits.loginRequestWindowSeconds,
    )


@sensitive_variables()
def apply_api_key_authentication_rate_limit(clientAddress: str) -> int:
    """Bound Bearer authentication work by source, shared across keys and failed attempts."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    # TODO: Business endpoints must also share organization budgets with web and client requests.
    return _apply_source_rate_limit(
        clientAddress,
        scope="accounts.api_key_authentication",
        maxRequests=limits.apiKeyRequestsPerSource,
        windowSeconds=limits.apiKeyRequestWindowSeconds,
    )


@sensitive_variables()
def apply_executor_client_rate_limit(clientAddress: str) -> int:
    """Limit Executor contact by source IP with a counter independent of Editor."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_rate_limit(
        clientAddress,
        scope="executors.client",
        maxRequests=limits.nativeClientRequestsPerSource,
        windowSeconds=limits.nativeClientRequestWindowSeconds,
    )


@sensitive_variables()
def apply_editor_client_rate_limit(clientAddress: str) -> int:
    """Limit Editor contact by source IP with a counter independent of Executor."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_rate_limit(
        clientAddress,
        scope="accounts.editor_client",
        maxRequests=limits.nativeClientRequestsPerSource,
        windowSeconds=limits.nativeClientRequestWindowSeconds,
    )


@sensitive_variables()
def apply_native_resource_authentication_rate_limit(clientAddress: str) -> int:
    """Keep Python resource traffic from exhausting native heartbeat and control budgets."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_rate_limit(
        clientAddress,
        scope="accounts.native_resource_authentication",
        maxRequests=limits.nativeClientRequestsPerSource,
        windowSeconds=limits.nativeClientRequestWindowSeconds,
    )


@sensitive_variables()
def apply_api_key_creation_rate_limit(clientAddress: str, *, actorId: str) -> int:
    """Limit credential creation separately; revoking a key never consumes this allowance."""
    return _apply_sensitive_action_rate_limit(
        clientAddress, actorId=actorId, scope="accounts.api_key_creation"
    )


@sensitive_variables()
def apply_password_change_rate_limit(clientAddress: str, *, actorId: str) -> int:
    """Limit signed-in password changes by source IP and the authenticated account ID.

    Counters commit before credential checks and remain independent of login requests.
    """
    return _apply_sensitive_action_rate_limit(
        clientAddress, actorId=actorId, scope="accounts.password_change"
    )


@sensitive_variables()
def apply_session_revocation_rate_limit(clientAddress: str, *, actorId: str) -> int:
    """Limit requests to sign out other sessions independently from login and password changes."""
    return _apply_sensitive_action_rate_limit(
        clientAddress, actorId=actorId, scope="accounts.session_revocation"
    )


@sensitive_variables()
def apply_account_deletion_rate_limit(clientAddress: str, *, actorId: str) -> int:
    """Limit deletion attempts by the source IP and acting account, across all targets."""
    return _apply_sensitive_action_rate_limit(
        clientAddress, actorId=actorId, scope="accounts.account_deletion"
    )


@sensitive_variables()
def apply_organization_deletion_rate_limit(clientAddress: str, *, actorId: str) -> int:
    """Limit password checks for scheduling organization deletion; cancellation stays available."""
    return _apply_sensitive_action_rate_limit(
        clientAddress, actorId=actorId, scope="organizations.deletion"
    )


@sensitive_variables()
def apply_password_reset_email_rate_limit(clientAddress: str) -> int:
    """Count all recovery-email requests, including unknown and suppressed addresses."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return _apply_source_rate_limit(
        clientAddress,
        scope="accounts.password_reset_email",
        maxRequests=limits.publicEmailRequestsPerSource,
        windowSeconds=limits.publicEmailRequestWindowSeconds,
    )


@sensitive_variables()
def apply_password_reset_token_rate_limit(clientAddress: str, *, token: str) -> int:
    """Share source and proof limits across reset-link checks and final submissions."""
    return _apply_email_token_rate_limit(
        clientAddress, token=token, scope="accounts.password_reset_token"
    )


@sensitive_variables()
def apply_email_change_email_rate_limit(clientAddress: str, *, actorId: str) -> int:
    """Limit authenticated email-change attempts, including failed password checks."""
    return _apply_sensitive_action_rate_limit(
        clientAddress, actorId=actorId, scope="accounts.email_change_email"
    )


@sensitive_variables()
def apply_email_change_token_rate_limit(clientAddress: str, *, token: str) -> int:
    """Share source and proof limits across email-change checks and confirmations."""
    return _apply_email_token_rate_limit(
        clientAddress, token=token, scope="accounts.email_change_token"
    )


@sensitive_variables()
def apply_invitation_email_rate_limit(clientAddress: str, *, actorId: str) -> int:
    """Limit administrator invitation requests independently from public registration."""
    return _apply_sensitive_action_rate_limit(
        clientAddress, actorId=actorId, scope="accounts.invitation_email"
    )
