# FileName: validators.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError


def validate_time_zone(timeZone: str) -> None:
    """Validate a stored time zone identifier without silently changing its spelling."""
    try:
        ZoneInfo(timeZone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(
            "Select a valid time zone, such as UTC or Asia/Taipei.",
            code="invalid_time_zone",
        ) from None
