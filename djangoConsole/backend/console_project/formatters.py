# FileName: formatters.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime

from django.utils import timezone


def format_instance_time(value: datetime | None) -> str:
    if value is None:
        return "-"
    return timezone.localtime(value, timezone.get_default_timezone()).isoformat(
        timespec="seconds"
    )


def format_file_size(sizeBytes: int, *, includeBytes: bool = False) -> str:
    if sizeBytes < 1024:
        return f"{sizeBytes} B"
    if sizeBytes < 1024**2:
        strSize = f"{sizeBytes / 1024:.1f} KiB"
    elif sizeBytes < 1024**3:
        strSize = f"{sizeBytes / 1024**2:.1f} MiB"
    else:
        strSize = f"{sizeBytes / 1024**3:.2f} GiB"
    return f"{strSize} ({sizeBytes:,} B)" if includeBytes else strSize
