# FileName: run_activity.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.utils import timezone

from runs.models import Run

_INT_ACTIVITY_DAYS = 14


@dataclass(frozen=True)
class RunActivitySummary:
    windowStart: datetime
    windowEnd: datetime
    averageConcurrentRuns: tuple[Decimal, ...]
    incompleteRunCount: int
    updatedAt: datetime


def load_run_activity() -> RunActivitySummary:
    """Average known Run durations by UTC hour across fourteen complete days."""
    if connection.vendor != "postgresql":
        raise ImproperlyConfigured("Run activity statistics require PostgreSQL.")
    currentTime = timezone.now().astimezone(UTC)
    windowEnd = currentTime.replace(hour=0, minute=0, second=0, microsecond=0)
    windowStart = windowEnd - timedelta(days=_INT_ACTIVITY_DAYS)

    # Generate UTC hours directly; duration overlaps are half-open and stay in SQL.
    strRunTable = connection.ops.quote_name(Run._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH hours AS (
                SELECT
                    hour_index,
                    %(start)s::timestamptz
                        + hour_index * INTERVAL '1 hour' AS hour_start
                FROM generate_series(0, %(hour_count)s - 1) AS hour_series(hour_index)
            )
            SELECT
                MOD(hours.hour_index, 24) AS hour,
                COALESCE(
                    SUM(
                        EXTRACT(EPOCH FROM (
                            LEAST(run.ended_at, hours.hour_start + INTERVAL '1 hour')
                            - GREATEST(run.started_at, hours.hour_start)
                        ))
                    ) FILTER (WHERE run.started_at IS NOT NULL),
                    0
                ) / %(seconds_per_hour)s AS average_concurrent_runs
            FROM hours
            LEFT JOIN {strRunTable} AS run
                ON run.started_at < hours.hour_start + INTERVAL '1 hour'
                AND run.ended_at > hours.hour_start
                AND run.ended_at > run.started_at
            GROUP BY MOD(hours.hour_index, 24)
            ORDER BY hour
            """,
            {
                "start": windowStart,
                "hour_count": _INT_ACTIVITY_DAYS * 24,
                "seconds_per_hour": _INT_ACTIVITY_DAYS * 3600,
            },
        )
        tupleAverage = tuple(Decimal(average) for _, average in cursor.fetchall())

    # These retained records may have started before the window; do not invent an end.
    intIncompleteRunCount = Run.objects.filter(
        ended_at__isnull=True, started_at__lt=windowEnd
    ).count()
    return RunActivitySummary(
        windowStart=windowStart,
        windowEnd=windowEnd,
        averageConcurrentRuns=tupleAverage,
        incompleteRunCount=intIncompleteRunCount,
        updatedAt=currentTime,
    )
