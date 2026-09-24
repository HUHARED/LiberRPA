# FileName: health.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

_LOGGER = logging.getLogger("console.health")


@never_cache
@require_safe
def check_liveness(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@never_cache
@require_safe
def check_database(_request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        _LOGGER.exception("Database health check failed.")
        # The public probe must not expose connection details or credentials.
        return JsonResponse({"status": "unavailable"}, status=503)

    return JsonResponse({"status": "ok"})
