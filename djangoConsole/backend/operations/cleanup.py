# FileName: cleanup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from django.db import DatabaseError
from django.utils import timezone

from .models import CleanupTask, CleanupStatus, CleanupState

_LOGGER = logging.getLogger("console.cleanup")
DICT_CLEANUP_INTERVAL_SECONDS = {
    CleanupTask.FILE_STORAGE: 60,
    CleanupTask.RUN_DATA: 3600,
    CleanupTask.EMAIL_HISTORY: 3600,
    CleanupTask.AUDIT_HISTORY: 3600,
    CleanupTask.API_KEYS: 3600,
}
DICT_CLEANUP_MAX_AGE_SECONDS = {
    task: 2 * intInterval for task, intInterval in DICT_CLEANUP_INTERVAL_SECONDS.items()
}


@contextmanager
def record_cleanup(task: CleanupTask) -> Generator[None]:
    """Record one attempt without wrapping cleanup work in a shared transaction or lock."""
    attemptId = uuid.uuid4()
    CleanupState.objects.update_or_create(
        task=task,
        defaults={
            "attempt_id": attemptId,
            "started_at": timezone.now(),
            "finished_at": None,
            "status": CleanupStatus.RUNNING,
        },
    )
    try:
        yield
    except DatabaseError:
        # Do not reconnect or issue another query just to report a database failure.
        raise
    except Exception:
        try:
            CleanupState.objects.filter(task=task, attempt_id=attemptId).update(
                status=CleanupStatus.FAILED, finished_at=timezone.now()
            )
        except DatabaseError as e:
            _LOGGER.warning("Could not record cleanup failure: %s", type(e).__name__)
        raise
    else:
        # A later overlapping attempt owns the latest state, even if this attempt finishes last.
        CleanupState.objects.filter(task=task, attempt_id=attemptId).update(
            status=CleanupStatus.SUCCEEDED, finished_at=timezone.now()
        )
