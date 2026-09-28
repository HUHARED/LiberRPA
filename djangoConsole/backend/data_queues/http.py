# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Concatenate, cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from pydantic import ValidationError as ContractValidationError

from accounts.api_key_authentication import (
    InvalidApiKeyError,
    ApiKeyAuthenticationContext,
    authenticate_api_key,
)
from accounts.models import User
from accounts.rate_limits import reserve_api_key_authentication_request
from accounts.session_revocation import SessionInvalidatedError, lock_session_write_access
from console_project.contracts import JsonRequest, JsonResponsePayload
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
    build_rate_limited_response,
)
from organizations.models import Membership, Department
from organizations.validators import normalize_path_name
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
)

from .contracts import MAX_QUEUE_RESPONSE_BYTES, QueueMutationRequest
from .models import DataQueue, QueueItem
from .services import QueueOperationError

_LOGGER = logging.getLogger("console.data_queues")


class QueueRequestError(Exception):
    """A malformed HTTP parameter, not an internal response or persistence error."""


_HANDLED_ERRORS = (
    PermissionDenied,
    InvalidApiKeyError,
    DataQueue.DoesNotExist,
    QueueItem.DoesNotExist,
    Department.DoesNotExist,
    QueueOperationError,
    QueueRequestError,
    InvalidPage,
    ValidationError,
    ContractValidationError,
    DatabaseError,
    ImproperlyConfigured,
)


def _build_queue_error_response(e: Exception) -> JsonResponse:
    if isinstance(e, (SessionInvalidatedError, InvalidApiKeyError)):
        response = build_error_response(
            "api_key_authentication_required"
            if isinstance(e, InvalidApiKeyError)
            else "authentication_required",
            "Valid credentials are required.",
            statusCode=401,
        )
        if isinstance(e, InvalidApiKeyError):
            response["WWW-Authenticate"] = (
                'Bearer realm="LiberRPA Console", error="invalid_token"'
            )
        return response
    if isinstance(e, PermissionDenied):
        return build_error_response(
            "queue_access_required",
            "Queue access is unavailable.",
            statusCode=403,
        )
    if isinstance(
        e,
        (DataQueue.DoesNotExist, QueueItem.DoesNotExist, Department.DoesNotExist),
    ):
        return build_error_response(
            "queue_not_found",
            "The queue, item, or department is unavailable.",
            statusCode=404,
        )
    if isinstance(e, QueueOperationError):
        return build_error_response(e.code, str(e), statusCode=409)
    if isinstance(e, QueueRequestError):
        return build_error_response("invalid_request", str(e), statusCode=400)
    if isinstance(e, InvalidPage):
        return build_error_response(
            "invalid_page",
            "The requested page is unavailable.",
            statusCode=400,
        )
    if isinstance(e, ValidationError):
        if getattr(e, "code", None) == "queue_response_too_large":
            return build_error_response(
                "queue_response_too_large",
                e.messages[0],
                statusCode=409,
            )
        fields: dict[str, list[str]] = {}
        duplicate = False
        if hasattr(e, "error_dict"):
            for fieldName, fieldErrors in e.error_dict.items():
                for fieldError in fieldErrors:
                    isDuplicate = fieldError.code == "duplicate_queue_name"
                    duplicate = duplicate or isDuplicate
                    fields.setdefault("name" if isDuplicate else fieldName, []).extend(
                        fieldError.messages
                    )
        else:
            fields["__all__"] = e.messages
        return build_error_response(
            "duplicate_queue_name" if duplicate else "invalid_queue",
            "Some queue fields are invalid.",
            statusCode=409 if duplicate else 400,
            fields=fields,
        )
    if isinstance(e, ContractValidationError):
        # Request-schema failures have already been handled by parse_json_request().
        _LOGGER.exception("Invalid queue response or receipt contract.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )
    return build_service_unavailable_response()


def session_queue_view[**P](
    view: Callable[Concatenate[HttpRequest, Membership, P], HttpResponse],
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    """Share browser authentication and error translation; views own parsing and transactions."""

    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required",
                "Sign in to continue.",
                statusCode=401,
            )
        try:
            membership = get_current_membership(actorId=cast(User, request.user).id)
            return view(request, membership, *args, **kwargs)
        except _HANDLED_ERRORS as e:
            return _build_queue_error_response(e)

    return wrapped


def api_queue_view[**P](
    view: Callable[
        Concatenate[HttpRequest, ApiKeyAuthenticationContext, P], HttpResponse
    ],
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    """Authenticate only the Bearer key; browser cookies never establish this identity."""

    @csrf_exempt
    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        try:
            retryAfter = reserve_api_key_authentication_request(
                request.META.get("REMOTE_ADDR", ""),
            )
            if retryAfter:
                return build_rate_limited_response(retryAfter)
            authentication = authenticate_api_key(
                request.headers.get("Authorization", "")
            )
            return view(request, authentication, *args, **kwargs)
        except _HANDLED_ERRORS as e:
            return _build_queue_error_response(e)

    return wrapped


def lock_queue_session_access(
    request: HttpRequest, membership: Membership
) -> OrganizationAccessContext:
    return lock_session_write_access(
        membership.user_id,
        membership.organization_id,
        AccessChannel.SESSION,
        request.session.get(HASH_SESSION_KEY, ""),
        request.session.get_expiry_date(),
    )


def parse_queue_request[Payload: JsonRequest](
    request: HttpRequest, requestSchema: type[Payload]
) -> Payload | JsonResponse:
    if request.GET:
        raise QueueRequestError(
            "Use the request body; query parameters are not accepted."
        )
    return parse_json_request(
        request, requestSchema, maxBodyBytes=MAX_QUEUE_RESPONSE_BYTES
    )


def normalize_queue_path(path: str) -> str:
    listPart = path.replace("\\", "/").removeprefix("/").split("/")
    if len(listPart) < 2 or len(listPart) > 65:
        raise ValidationError("Use a full department path and queue name.")
    return "/" + "/".join(normalize_path_name(part) for part in listPart)


def parse_item_request[Payload: QueueMutationRequest](
    request: HttpRequest,
    requestSchema: type[Payload],
    *,
    queueId: uuid.UUID | None = None,
) -> tuple[uuid.UUID | str, Payload] | JsonResponse:
    payload = parse_queue_request(request, requestSchema)
    if isinstance(payload, JsonResponse):
        return payload
    if queueId is not None:
        if payload.queue_path is not None:
            raise QueueRequestError(
                "The browser endpoint identifies its queue in the URL."
            )
        return queueId, payload
    if payload.queue_path is None:
        raise QueueRequestError("queue_path is required.")
    return normalize_queue_path(payload.queue_path), payload


def build_queue_response(
    payload: JsonResponsePayload,
    *,
    statusCode: int = 200,
) -> HttpResponse:
    content = payload.model_dump_json().encode("utf-8")
    if len(content) > MAX_QUEUE_RESPONSE_BYTES:
        raise QueueOperationError(
            "queue_response_too_large",
            "The response exceeds the byte limit.",
        )
    return HttpResponse(content, status=statusCode, content_type="application/json")
