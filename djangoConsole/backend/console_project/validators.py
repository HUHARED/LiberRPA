# FileName: validators.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError

from .contracts import JsonValue


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
        if depth > 64:
            raise ValueError("JSON must not exceed 64 levels of nesting.")
        if type(child) is int and abs(child) > 2**53 - 1:
            raise ValueError(
                "Integers must be between -9007199254740991 and 9007199254740991.",
            )
        if type(child) is float and (
            not math.isfinite(child) or (child.is_integer() and abs(child) > 2**53 - 1)
        ):
            raise ValueError(
                "Use finite numbers and integers within the safe integer range.",
            )
        if isinstance(child, dict):
            for key, entry in child.items():
                key.encode("utf-8")
                validate_child(entry, depth + 1)
        elif isinstance(child, list):
            for entry in child:
                validate_child(entry, depth + 1)
        elif isinstance(child, str):
            child.encode("utf-8")

    validate_child(value, 0)
