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

from accounts.api_key_authentication import InvalidApiKeyError
from accounts.resource_authentication import (
    InvalidResourceCredentialError,
    ResourceAuthenticationContext,
    build_resource_authentication_required_response,
    authenticate_resource_request,
)
from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError, lock_session_write_access
from console_project.contracts import JsonRequest, JsonResponsePayload
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.models import Membership, Department
from organizations.validators import parse_resource_path
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
    InvalidResourceCredentialError,
    SessionInvalidatedError,
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
    if isinstance(e, (InvalidApiKeyError, InvalidResourceCredentialError)):
        return build_resource_authentication_required_response()
    if isinstance(e, SessionInvalidatedError):
        return build_authentication_required_response()
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
        boolDuplicate = False
        if hasattr(e, "error_dict"):
            for strFieldName, fieldErrors in e.error_dict.items():
                for fieldError in fieldErrors:
                    boolIsDuplicate = fieldError.code == "duplicate_queue_name"
                    boolDuplicate = boolDuplicate or boolIsDuplicate
                    fields.setdefault(
                        "name" if boolIsDuplicate else strFieldName, []
                    ).extend(fieldError.messages)
        else:
            fields["__all__"] = e.messages
        return build_error_response(
            "duplicate_queue_name" if boolDuplicate else "invalid_queue",
            "Some queue fields are invalid.",
            statusCode=409 if boolDuplicate else 400,
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
            return build_authentication_required_response()
        try:
            membership = get_current_membership(actorId=cast(User, request.user).id)
            return view(request, membership, *args, **kwargs)
        except _HANDLED_ERRORS as e:
            return _build_queue_error_response(e)

    return wrapped


def api_queue_view[**P](
    view: Callable[
        Concatenate[HttpRequest, ResourceAuthenticationContext, P], HttpResponse
    ],
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    """Authenticate the Bearer key or native session; cookies never establish identity."""

    @csrf_exempt
    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        try:
            authentication = authenticate_resource_request(request)
            if isinstance(authentication, JsonResponse):
                return authentication
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
        request.session.session_key,
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


def parse_item_request[Payload: QueueMutationRequest](
    request: HttpRequest,
    requestSchema: type[Payload],
    *,
    queueId: uuid.UUID | None = None,
) -> tuple[uuid.UUID | tuple[str, ...], Payload] | JsonResponse:
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
    return parse_resource_path(payload.queue_path), payload


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
