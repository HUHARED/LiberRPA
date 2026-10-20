# FileName: run_activity.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime, time, timedelta, UTC
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import connection
from django.utils import timezone

from runs.models import Run

from .contracts import RunActivityHourResponse, RunActivityResponse

_INT_ACTIVITY_DAYS = 14


def load_run_activity() -> RunActivityResponse:
    instanceZone = ZoneInfo(settings.TIME_ZONE)
    endDate = timezone.now().astimezone(instanceZone).date()
    startDate = endDate - timedelta(days=_INT_ACTIVITY_DAYS)
    windowStart = datetime.combine(startDate, time.min, instanceZone).astimezone(UTC)
    windowEnd = datetime.combine(endDate, time.min, instanceZone).astimezone(UTC)

    # This bounded calendar scan also keeps repeated hours and half-hour daylight-saving changes separate.
    listBoundary: list[datetime] = []
    listHour: list[int] = []
    previousHour = None
    previousLocalTime = None
    currentTime = windowStart
    minuteInterval = timedelta(minutes=1)
    while currentTime < windowEnd:
        localTime = currentTime.astimezone(instanceZone)
        localClock = localTime.replace(tzinfo=None)
        hourKey = (localTime.date(), localTime.hour)
        if hourKey != previousHour or (
            previousLocalTime is not None and localClock < previousLocalTime
        ):
            listBoundary.append(currentTime)
            listHour.append(localTime.hour)
            previousHour = hourKey
        previousLocalTime = localClock
        currentTime += minuteInterval
    listBoundary.append(windowEnd)

    # Aggregate execution times in the database without loading tenant details into Python.
    strRunTable = connection.ops.quote_name(Run._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH run_buckets AS (
                SELECT
                    width_bucket(
                        GREATEST(started_at, %(start)s), %(boundaries)s::timestamptz[]
                    ) AS first_bucket,
                    width_bucket(
                        GREATEST(
                            started_at,
                            LEAST(ended_at, %(end)s) - INTERVAL '1 microsecond'
                        ),
                        %(boundaries)s::timestamptz[]
                    ) AS last_bucket
                FROM {strRunTable}
                WHERE started_at < %(end)s
                    AND ended_at >= %(start)s
                    AND (ended_at > %(start)s OR started_at = ended_at)
            )
            SELECT hour_values.hour, COUNT(*)
            FROM run_buckets
            CROSS JOIN LATERAL generate_series(first_bucket, last_bucket) AS buckets(id)
            JOIN unnest(%(hours)s::integer[]) WITH ORDINALITY AS hour_values(hour, id)
                ON hour_values.id = buckets.id
            GROUP BY hour_values.hour
            """,
            {
                "start": windowStart,
                "end": windowEnd,
                "boundaries": listBoundary,
                "hours": listHour,
            },
        )
        dictRunCount = {
            int(intHour): int(intCount) for intHour, intCount in cursor.fetchall()
        }

    intIncompleteRunCount = Run.objects.filter(
        ended_at__isnull=True, started_at__lt=windowEnd
    ).count()
    return RunActivityResponse(
        time_zone=settings.TIME_ZONE,
        start_date=startDate,
        end_date=endDate - timedelta(days=1),
        updated_at=timezone.now(),
        hours=[
            RunActivityHourResponse(hour=intHour, run_count=dictRunCount.get(intHour, 0))
            for intHour in range(24)
        ],
        incomplete_run_count=intIncompleteRunCount,
    )
