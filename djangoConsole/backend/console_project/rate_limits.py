# FileName: rate_limits.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import math
import time
from datetime import timedelta
from threading import Lock

from django.db import transaction
from django.utils import timezone

from accounts.models import RequestRateLimit

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
            listExpiredKeyHash = list(
                RequestRateLimit.objects
                .select_for_update(skip_locked=True)
                .filter(expires_at__lte=timezone.now())
                .order_by("expires_at", "key_hash")
                .values_list("key_hash", flat=True)[:_INT_PRUNE_BATCH_SIZE]
            )
            if listExpiredKeyHash:
                RequestRateLimit.objects.filter(key_hash__in=listExpiredKeyHash).delete()
    finally:
        _LOCK_PRUNING.release()


def apply_request_rate_limit(
    keyHash: str, *, maxRequests: int, windowSeconds: int, cost: int = 1
) -> int:
    """Consume a weighted attempt, returning zero when admitted or retry seconds when full.

    Call before a business transaction; admitted attempts remain charged if later work fails.
    """
    if cost < 1:
        raise ValueError("Request cost must be positive.")
    _delete_expired_request_counters_if_due()
    requestWindow = timedelta(seconds=windowSeconds)
    # Commit each counter before business work; failures do not refund attempts.
    with transaction.atomic(durable=True):
        requestLimit, _ = RequestRateLimit.objects.select_for_update().get_or_create(
            key_hash=keyHash,
            defaults={"expires_at": timezone.now() + requestWindow},
        )
        # Recheck time after any wait for another request using the same counter.
        currentTime = timezone.now()
        boolWindowExpired = requestLimit.expires_at <= currentTime
        if boolWindowExpired:
            requestLimit.request_count = 0
            requestLimit.expires_at = currentTime + requestWindow

        if requestLimit.request_count + cost > maxRequests:
            if boolWindowExpired:
                requestLimit.save(update_fields=["request_count", "expires_at"])
            return max(
                1, math.ceil((requestLimit.expires_at - currentTime).total_seconds())
            )

        requestLimit.request_count += cost
        requestLimit.save(update_fields=["request_count", "expires_at"])
    return 0
