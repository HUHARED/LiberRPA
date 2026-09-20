# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


# Preserve the existing account imports while sharing one HTTP implementation.
from console_project.http import (
    JsonRequest as AccountRequest,
    build_error_response,
    build_rate_limited_response,
    parse_json_request,
)

__all__ = [
    "AccountRequest",
    "build_error_response",
    "build_rate_limited_response",
    "parse_json_request",
]
