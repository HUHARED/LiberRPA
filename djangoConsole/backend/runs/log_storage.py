# FileName: log_storage.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Sequence
from datetime import datetime

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from .contracts import JobState
from .models import Run, RunLog, RunLogUsage


def get_or_create_run_log_usage(organizationId: uuid.UUID) -> RunLogUsage:
    """Read counters under the caller's organization lock and transaction."""
    usage, _ = RunLogUsage.objects.get_or_create(organization_id=organizationId)
    return usage


def clear_run_logs(usage: RunLogUsage, runs: Sequence[Run], clearedAt: datetime) -> None:
    """Clear trusted Run groups and their counters in the same organization transaction."""
    if not runs:
        return
    listRunId = [run.pk for run in runs]
    intBytes = sum(run.log_bytes for run in runs)
    intGroups = sum(run.log_bytes > 0 for run in runs)
    RunLog.objects.filter(run_id__in=listRunId).delete()
    Run.objects.filter(pk__in=listRunId).update(log_bytes=0, logs_cleared_at=clearedAt)
    if intBytes or intGroups:
        usage.used_bytes -= intBytes
        usage.group_count -= intGroups
        usage.save(update_fields=["used_bytes", "group_count"])
    for run in runs:
        run.log_bytes = 0
        run.logs_cleared_at = clearedAt


def get_clearable_log_runs(organizationId: uuid.UUID) -> QuerySet[Run]:
    """Keep active, retrying and unresolved Jobs outside log eviction."""
    return (
        Run.objects
        .filter(
            job__request__organization_id=organizationId,
            job__state=JobState.FINISHED,
            logs_cleared_at__isnull=True,
        )
        .select_related("job")
        .only("id", "log_bytes", "job__closed_at", "job__ended_at")
        .order_by("job__ended_at", "started_at", "id")
    )


def make_run_log_space(usage: RunLogUsage, run: Run, addedBytes: int) -> bool:
    """Evict only enough eligible history to admit this batch, or leave it untouched."""
    limits = settings.CONSOLE_LIMITS
    intAddedGroups = int(run.log_bytes == 0)
    intRequiredBytes = usage.used_bytes + addedBytes
    intRequiredGroups = usage.group_count + intAddedGroups
    if (
        intRequiredBytes <= limits.maxRunLogBytesPerOrganization
        and intRequiredGroups <= limits.maxRunLogGroupsPerOrganization
    ):
        return True
    # The uploading Run is retained; its own logs cannot be cleared and then re-created.
    if (
        run.log_bytes + addedBytes > limits.maxRunLogBytesPerOrganization
        or limits.maxRunLogGroupsPerOrganization == 0
    ):
        return False
    listExpiredRun: list[Run] = []
    for previousRun in (
        get_clearable_log_runs(usage.organization_id)
        .filter(log_bytes__gt=0)
        .exclude(pk=run.pk)
        .iterator(chunk_size=200)
    ):
        listExpiredRun.append(previousRun)
        intRequiredBytes -= previousRun.log_bytes
        intRequiredGroups -= 1
        if (
            intRequiredBytes <= limits.maxRunLogBytesPerOrganization
            and intRequiredGroups <= limits.maxRunLogGroupsPerOrganization
        ):
            clear_run_logs(usage, listExpiredRun, timezone.now())
            return True
    return False


def add_run_log_usage(usage: RunLogUsage, run: Run, addedBytes: int) -> None:
    """Account only for newly inserted rows after duplicate identities were removed."""
    usage.used_bytes += addedBytes
    usage.group_count += int(run.log_bytes == 0)
    run.log_bytes += addedBytes
    run.save(update_fields=["log_bytes"])
    usage.save(update_fields=["used_bytes", "group_count"])
