# FileName: cron.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import re
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, CroniterBadDateError, croniter
from django.core.exceptions import ValidationError

_RE_CRON_FIELD = re.compile(r"[0-9*,/\-]+\Z")


def normalize_cron(expression: str) -> str:
    listField = expression.upper().split()
    if len(listField) == 5:
        listField.insert(0, "0")
    if len(listField) != 6 or any(
        _RE_CRON_FIELD.fullmatch(strField) is None for strField in listField
    ):
        raise ValidationError({
            "cron": "Use five fields or six fields with seconds first."
        })
    for strField in listField:
        for strPart in strField.split(","):
            # Both clients reject ranges whose start is greater than their end; do not let the Cron library wrap them around.
            strRange = strPart.split("/")[0]
            if "-" in strRange and strRange.replace("-", "").isdigit():
                listBound = strRange.split("-")
                if len(listBound) != 2 or int(listBound[0]) > int(listBound[1]):
                    raise ValidationError({"cron": "Cron ranges must be ascending."})
    if listField[5] != "*":
        setWeekday = set()
        try:
            for strPart in listField[5].split(","):
                listStep = strPart.split("/")
                if len(listStep) > 2:
                    raise ValueError
                intStep = int(listStep[1]) if len(listStep) == 2 else 1
                if intStep < 1:
                    raise ValueError
                strRange = listStep[0]
                if strRange == "*":
                    intStart, intEnd = 0, 7
                elif "-" in strRange:
                    intStart, intEnd = map(int, strRange.split("-"))
                else:
                    intStart = int(strRange)
                    intEnd = 7 if len(listStep) == 2 else intStart
                if not 0 <= intStart <= intEnd <= 7:
                    raise ValueError
                setWeekday.update(
                    intValue % 7 for intValue in range(intStart, intEnd + 1, intStep)
                )
        except ValueError:
            raise ValidationError({"cron": "The day-of-week field is invalid."}) from None
        listField[5] = ",".join(map(str, sorted(setWeekday)))
    strCron = " ".join(listField)
    if not croniter.is_valid(strCron, second_at_beginning=True):
        raise ValidationError({"cron": "The Cron expression is invalid."})
    return strCron


def get_schedule_zone(timeZone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timeZone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError({"time_zone": "Select a valid IANA time zone."}) from None


def get_next_trigger(
    cron: str, timeZone: str, activeFrom: datetime, activeUntil: datetime, after: datetime
) -> datetime | None:
    """Check local times, skip times missing during a daylight-saving change, and use the first occurrence of repeated times."""
    zone = get_schedule_zone(timeZone)
    lowerBound = max(after, activeFrom - timedelta(microseconds=1))
    if lowerBound >= activeUntil:
        return None
    localBase = lowerBound.astimezone(zone).replace(tzinfo=None)
    iterator = croniter(
        cron,
        localBase,
        day_or=True,
        second_at_beginning=True,
        max_years_between_matches=100,
    )
    try:
        while True:
            localCandidate = iterator.get_next(datetime)
            candidate = localCandidate.replace(tzinfo=zone, fold=0).astimezone(UTC)
            # Skip local times missing during a daylight-saving change before their converted UTC values can end the search.
            if candidate.astimezone(zone).replace(tzinfo=None) != localCandidate:
                continue
            if candidate >= activeUntil:
                return None
            if candidate <= after or candidate < activeFrom:
                continue
            return candidate
    except (CroniterBadDateError, CroniterBadCronError):
        return None


def preview_triggers(
    cron: str,
    timeZone: str,
    activeFrom: datetime,
    activeUntil: datetime,
    after: datetime,
    count: int = 5,
) -> list[datetime]:
    listTrigger = []
    for _ in range(count):
        nextTime = get_next_trigger(cron, timeZone, activeFrom, activeUntil, after)
        if nextTime is None:
            break
        listTrigger.append(nextTime)
        after = nextTime
    return listTrigger
