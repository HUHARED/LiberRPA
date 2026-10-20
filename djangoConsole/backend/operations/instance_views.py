# FileName: instance_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
)

from .access import get_platform_actor
from .contracts import InstanceHistoryRange
from .instance_status import load_instance_summary
from .monitoring import MonitoringUnavailableError, load_instance_status

_LOGGER = logging.getLogger("console.monitoring")


@never_cache
@require_GET
def get_instance_summary(request: HttpRequest) -> JsonResponse:
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.GET:
            return build_error_response(
                "invalid_instance_summary_query",
                "This request does not accept query parameters.",
                statusCode=400,
            )

        response = load_instance_summary()
        return JsonResponse(response.model_dump(mode="json"))
    except PermissionDenied:
        return build_error_response(
            "platform_access_required",
            "Platform administrator access is required.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_GET
def get_instance_status(request: HttpRequest) -> JsonResponse:
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        query = request.GET
        if set(query) - {"range", "network_interface"} or any(
            len(query.getlist(strKey)) > 1 for strKey in query
        ):
            raise ValueError("Invalid instance status filters.")
        historyRange = InstanceHistoryRange(query.get("range", InstanceHistoryRange.DAY))
        strNetworkInterface = query.get("network_interface")
        if strNetworkInterface is not None and (
            not strNetworkInterface
            or strNetworkInterface == "lo"
            or len(strNetworkInterface) > 128
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in strNetworkInterface
            )
        ):
            raise ValueError("Invalid network interface.")

        response = load_instance_status(
            settings.CONSOLE_MONITORING, historyRange, strNetworkInterface
        )
        return JsonResponse(response.model_dump(mode="python"))
    except PermissionDenied:
        return build_error_response(
            "platform_access_required",
            "Platform administrator access is required.",
            statusCode=403,
        )
    except ValueError:
        return build_error_response(
            "invalid_filters", "Invalid instance status filters.", statusCode=400
        )
    except MonitoringUnavailableError as e:
        _LOGGER.warning("Cannot read host monitoring data: %s", e)
        return build_error_response(
            "monitoring_unavailable",
            "Host monitoring is temporarily unavailable.",
            statusCode=503,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
