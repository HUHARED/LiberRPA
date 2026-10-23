# FileName: validators.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import math
import re
from datetime import date, datetime, time, timedelta, UTC
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError

from .contracts import JsonValue
from .constants import INT_MAX_JSON_INTEGER, INT_WINDOWS_NAME_MAX_LENGTH

_SET_RESERVED_WINDOWS_NAME = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{intIndex}" for intIndex in range(1, 10)),
    *(f"LPT{intIndex}" for intIndex in range(1, 10)),
}


def validate_windows_name(name: str) -> None:
    if (
        not name
        or name != name.strip()
        or name.endswith(".")
        or len(name.encode("utf-16-le")) // 2 > INT_WINDOWS_NAME_MAX_LENGTH
        or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
        or name.split(".", 1)[0].upper() in _SET_RESERVED_WINDOWS_NAME
    ):
        raise ValueError(f"Invalid Windows file or directory name: {name!r}.")


def validate_json_string(value: str) -> None:
    if "\0" in value:
        raise ValueError("JSON strings must not contain NUL characters.")
    value.encode("utf-8")


def validate_time_zone(timeZone: str) -> None:
    """Validate a stored time zone identifier without silently changing its spelling."""
    try:
        ZoneInfo(timeZone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(
            "Select a valid time zone, such as UTC or Asia/Taipei.",
            code="invalid_time_zone",
        ) from None


def validate_json_value(value: JsonValue) -> None:
    """Validate the shared JSON value rules, independently of resource-specific size limits."""

    def validate_child(child: JsonValue, depth: int) -> None:
        # Customized depth.
        if depth > 64:
            raise ValueError("JSON must not exceed 64 levels of nesting.")
        if type(child) is int and abs(child) > INT_MAX_JSON_INTEGER:
            raise ValueError(
                f"Integers must be between {-INT_MAX_JSON_INTEGER} and {INT_MAX_JSON_INTEGER}.",
            )
        if type(child) is float and (
            not math.isfinite(child)
            or (child.is_integer() and abs(child) > INT_MAX_JSON_INTEGER)
        ):
            raise ValueError(
                "Use finite numbers and integers within the safe integer range.",
            )
        if isinstance(child, dict):
            for strKey, entry in child.items():
                validate_json_string(strKey)
                validate_child(entry, depth + 1)
        elif isinstance(child, list):
            for entry in child:
                validate_child(entry, depth + 1)
        elif isinstance(child, str):
            validate_json_string(child)

    validate_child(value, 0)


def parse_zoned_time(value: str, timeZone: str) -> datetime:
    try:
        dateTime = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError("Use an ISO date and time.") from None
    if dateTime.tzinfo is not None:
        return dateTime.astimezone(UTC)
    validate_time_zone(timeZone)
    zone = ZoneInfo(timeZone)
    firstTime = dateTime.replace(tzinfo=zone, fold=0)
    utcTime = firstTime.astimezone(UTC)
    if utcTime.astimezone(zone).replace(tzinfo=None) != dateTime:
        raise ValidationError("This local time does not exist in the selected time zone.")
    if firstTime.utcoffset() != dateTime.replace(tzinfo=zone, fold=1).utcoffset():
        raise ValidationError("This local time is ambiguous. Include its UTC offset.")
    return utcTime


def parse_date_range(
    dateFrom: str | None, dateTo: str | None, timeZone: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """Parse inclusive date filters into local start and exclusive end times."""
    dictDate: dict[str, date] = {}
    for strField, strDate in (("date_from", dateFrom), ("date_to", dateTo)):
        if strDate is None:
            continue
        try:
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", strDate) is None:
                raise ValueError
            dictDate[strField] = date.fromisoformat(strDate)
        except ValueError:
            raise ValidationError({
                strField: "Enter a valid date in YYYY-MM-DD format."
            }) from None
    if (
        "date_from" in dictDate
        and "date_to" in dictDate
        and dictDate["date_from"] > dictDate["date_to"]
    ):
        raise ValidationError({
            "date_to": "The end date must not be earlier than the start date."
        })
    fromTime = (
        datetime.combine(dictDate["date_from"], time.min, timeZone)
        if "date_from" in dictDate
        else None
    )
    try:
        # The inclusive end date becomes the next local midnight, including 23/25-hour days.
        untilTime = (
            datetime.combine(dictDate["date_to"] + timedelta(days=1), time.min, timeZone)
            if "date_to" in dictDate
            else None
        )
    except OverflowError:
        raise ValidationError({"date_to": "Select an earlier end date."}) from None
    return fromTime, untilTime
