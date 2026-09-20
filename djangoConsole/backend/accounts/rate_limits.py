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

from .models import RegistrationRequestLimit

_PRUNE_BATCH_SIZE = 100


@transaction.atomic
def _prune_expired_limits() -> None:
    # Cleanup locks are released before taking the current counter's lock.
    # Skip active transactions and keep the work bounded for each request.
    expiredHashes = list(
        RegistrationRequestLimit.objects
        .select_for_update(skip_locked=True)
        .filter(expires_at__lte=timezone.now())
        .order_by("expires_at", "source_hash")
        .values_list("source_hash", flat=True)[:_PRUNE_BATCH_SIZE]
    )
    if expiredHashes:
        RegistrationRequestLimit.objects.filter(source_hash__in=expiredHashes).delete()


@sensitive_variables()
def _get_source_hash(clientAddress: str, *, scope: str) -> str:
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
    window = timedelta(seconds=windowSeconds)
    # Commit each counter before business work; failures do not refund attempts.
    with transaction.atomic(durable=True):
        counter, _created = (
            RegistrationRequestLimit.objects.select_for_update().get_or_create(
                source_hash=sourceHash,
                defaults={"expires_at": timezone.now() + window},
            )
        )
        # Recheck time after any wait for another request using the same counter.
        currentTime = timezone.now()
        expired = counter.expires_at <= currentTime
        if expired:
            counter.request_count = 0
            counter.expires_at = currentTime + window

        if counter.request_count >= maxRequests:
            if expired:
                counter.save(update_fields=["request_count", "expires_at"])
            return max(1, math.ceil((counter.expires_at - currentTime).total_seconds()))

        counter.request_count += 1
        counter.save(update_fields=["request_count", "expires_at"])
    return 0


@sensitive_variables()
def reserve_registration_email_request(clientAddress: str) -> int:
    """Count an HTTP request, returning zero when allowed or a Retry-After in seconds.

    The caller supplies the server's client address, never an untrusted HTTP header.
    The counter commits before the email service runs, including for suppressed requests.
    """
    sourceHash = _get_source_hash(
        clientAddress, scope="accounts.registration_email.source"
    )
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_limits()
    return _reserve_request(
        sourceHash,
        maxRequests=limits.registrationEmailRequestsPerSource,
        windowSeconds=limits.registrationEmailRequestWindowSeconds,
    )


@sensitive_variables()
def reserve_registration_token_request(clientAddress: str, *, token: str) -> int:
    """Limit link reads and registration submissions by both source IP and email proof."""
    sourceHash = _get_source_hash(
        clientAddress, scope="accounts.registration_token.source"
    )
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    _prune_expired_limits()
    retryAfter = _reserve_request(
        sourceHash,
        maxRequests=limits.registrationTokenRequestsPerSource,
        windowSeconds=limits.registrationTokenRequestWindowSeconds,
    )
    if retryAfter:
        return retryAfter

    # A source already over its limit cannot create more token counters.
    tokenHash = salted_hmac(
        "accounts.registration_token.proof", token, algorithm="sha256"
    ).hexdigest()
    return _reserve_request(
        tokenHash,
        maxRequests=limits.registrationTokenRequestsPerToken,
        windowSeconds=limits.registrationTokenRequestWindowSeconds,
    )
