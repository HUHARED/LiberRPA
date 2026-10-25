# FileName: middleware.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from collections.abc import Awaitable, Callable
from inspect import iscoroutinefunction
from time import perf_counter
from typing import cast

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpRequest, HttpResponseBase, JsonResponse
from django.utils.cache import add_never_cache_headers
from django.utils.decorators import sync_and_async_middleware
from django.utils.deprecation import MiddlewareMixin

from operations.audit_http import record_failed_request
from organizations.rate_limits import RequestBudgetError

from .http import build_error_response
from .logging import request_log_context

_LOGGER = logging.getLogger("console.http")

type _SyncResponseHandler = Callable[[HttpRequest], HttpResponseBase]
type _AsyncResponseHandler = Callable[[HttpRequest], Awaitable[HttpResponseBase]]


class OrganizationRequestBudgetMiddleware(MiddlewareMixin):
    def process_exception(
        self, _request: HttpRequest, exception: Exception
    ) -> JsonResponse | None:
        if not isinstance(exception, RequestBudgetError):
            return None
        response = build_error_response(
            exception.code, str(exception), statusCode=exception.status
        )
        if exception.retryAfterSeconds:
            response["Retry-After"] = str(exception.retryAfterSeconds)
        add_never_cache_headers(response)
        return response


def _record_request_result(
    request: HttpRequest, response: HttpResponseBase, startedAt: float
) -> None:
    record_failed_request(request, response)
    # Log route names, never a raw URL, query string, body, cookies, or authorization.
    strRoute = request.resolver_match.url_name if request.resolver_match else "unmatched"
    intLevel = (
        logging.ERROR
        if response.status_code >= 500
        else logging.WARNING
        if response.status_code >= 400
        else logging.DEBUG
        if strRoute in ("health-live", "health-database")
        else logging.INFO
    )
    if settings.CONSOLE_LOG_REQUESTS or response.status_code >= 400:
        _LOGGER.log(
            intLevel,
            "Request completed: method=%s route=%s status=%s duration_ms=%.1f.",
            request.method
            if request.method
            in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
            else "OTHER",
            strRoute,
            response.status_code,
            (perf_counter() - startedAt) * 1000,
        )


@sync_and_async_middleware
def request_logging(
    get_response: _SyncResponseHandler | _AsyncResponseHandler,
) -> _SyncResponseHandler | _AsyncResponseHandler:
    """Keep correlation local to each request in both WSGI and ASGI."""

    if iscoroutinefunction(get_response):

        async def async_middleware(request: HttpRequest) -> HttpResponseBase:
            with request_log_context() as requestId:
                floatStartedAt = perf_counter()
                response = await cast(_AsyncResponseHandler, get_response)(request)
                response["X-Request-ID"] = str(requestId)
                await sync_to_async(_record_request_result, thread_sensitive=True)(
                    request, response, floatStartedAt
                )
                return response

        return async_middleware

    def sync_middleware(request: HttpRequest) -> HttpResponseBase:
        with request_log_context() as requestId:
            floatStartedAt = perf_counter()
            response = cast(_SyncResponseHandler, get_response)(request)
            response["X-Request-ID"] = str(requestId)
            _record_request_result(request, response, floatStartedAt)
            return response

    return sync_middleware
