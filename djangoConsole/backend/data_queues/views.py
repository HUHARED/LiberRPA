# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from typing import cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from pydantic import BaseModel

from accounts.api_key_authentication import (
    InvalidApiKeyError,
    authenticate_api_key,
    lock_api_key_write_access,
)
from accounts.models import User
from accounts.rate_limits import reserve_api_key_authentication_request
from accounts.session_revocation import SessionInvalidatedError, lock_session_write_access
from console_project.http import (
    build_error_response,
    build_rate_limited_response,
    build_service_unavailable_response,
    parse_json_request,
    parse_page_number,
)
from organizations.http import parse_department_resource_filters
from organizations.models import Department
from organizations.permissions import (
    AccessChannel,
    get_current_membership,
    resolve_organization_access,
)

from .contracts import (
    QueueClaimRequest,
    QueueCreationRequest,
    QueueDeleteItemsRequest,
    QueueDeletionRequest,
    QueueDetailsRequest,
    QueueDetailsResponse,
    QueueItemDetailsResponse,
    QueueItemsResponse,
    QueueListResponse,
    QueueMutationResponse,
    QueueMutationRequest,
    QueueQueryRequest,
    QueueQueryResponse,
    QueueResetRequest,
    QueueUploadRequest,
)
from .models import DataQueue, QueueItem
from .queries import (
    build_item_payload,
    build_queue_payload,
    get_item_list,
    get_queue_list,
    get_queue_query,
    resolve_queue_path,
)
from .services import (
    MAX_QUEUE_RESPONSE_BYTES,
    QueueOperationError,
    delete_queue,
    mutate_items,
    query_items,
    save_queue,
)

_MUTATION_SCHEMA = {
    "upload": QueueUploadRequest,
    "claim": QueueClaimRequest,
    "reset": QueueResetRequest,
    "delete_items": QueueDeleteItemsRequest,
}


def _response(
    model: type[BaseModel], payload: dict[str, object], status: int = 200
) -> HttpResponse:
    serialized = json.dumps(
        payload,
        cls=DjangoJSONEncoder,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    content = model.model_validate_json(serialized).model_dump_json().encode("utf-8")
    if len(content) > MAX_QUEUE_RESPONSE_BYTES:
        raise QueueOperationError(
            "queue_response_too_large", "The response exceeds the byte limit."
        )
    return HttpResponse(content, status=status, content_type="application/json")


def _error(e: Exception) -> JsonResponse:
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
            "queue_access_required", "Queue access is unavailable.", statusCode=403
        )
    if isinstance(
        e, (DataQueue.DoesNotExist, QueueItem.DoesNotExist, Department.DoesNotExist)
    ):
        return build_error_response(
            "queue_not_found",
            "The queue, item, or department is unavailable.",
            statusCode=404,
        )
    if isinstance(e, QueueOperationError):
        return build_error_response(e.code, str(e), statusCode=409)
    if isinstance(e, InvalidPage):
        return build_error_response(
            "invalid_page", "The requested page is unavailable.", statusCode=400
        )
    if isinstance(e, ValidationError):
        duplicate = any(
            error.code == "duplicate_queue_name"
            for errors in getattr(e, "error_dict", {}).values()
            for error in errors
        )
        return build_error_response(
            "duplicate_queue_name" if duplicate else "invalid_queue",
            "Some queue fields are invalid.",
            statusCode=409 if duplicate else 400,
            fields=e.message_dict
            if hasattr(e, "error_dict")
            else {"__all__": e.messages},
        )
    if isinstance(e, ValueError):
        return build_error_response(
            "invalid_request",
            "Use supported fields, valid UUIDs, and valid queue filters.",
            statusCode=400,
        )
    return build_service_unavailable_response()


_HANDLED_ERRORS = (
    SessionInvalidatedError,
    InvalidApiKeyError,
    PermissionDenied,
    DataQueue.DoesNotExist,
    QueueItem.DoesNotExist,
    Department.DoesNotExist,
    QueueOperationError,
    InvalidPage,
    ValidationError,
    ValueError,
    DatabaseError,
    ImproperlyConfigured,
)


@never_cache
@sensitive_variables()
def queue_request(
    request: HttpRequest,
    *,
    action: str,
    queueId: uuid.UUID | None = None,
    itemId: uuid.UUID | None = None,
) -> HttpResponse:
    methods = (
        ["GET", "POST"]
        if action in ("list", "details")
        else ["GET"]
        if action in ("items", "item")
        else ["POST"]
    )
    if request.method not in methods:
        return HttpResponseNotAllowed(methods)
    if not request.user.is_authenticated:
        return build_error_response(
            "authentication_required", "Sign in to continue.", statusCode=401
        )
    try:
        membership = get_current_membership(actorId=cast(User, request.user).id)
        with transaction.atomic():
            if request.method == "GET":
                access = resolve_organization_access(
                    actorId=membership.user_id,
                    organizationId=membership.organization_id,
                    channel=AccessChannel.SESSION,
                )
                if action == "list":
                    return _response(
                        QueueListResponse,
                        get_queue_list(
                            access, **parse_department_resource_filters(request.GET)
                        ),
                    )
                queue = get_queue_query(access).get(pk=queueId)
                if action == "items":
                    if set(request.GET) - {"page", "status", "order", "item_id"} or any(
                        len(request.GET.getlist(key)) != 1 for key in request.GET
                    ):
                        raise ValueError("Unknown or repeated filters.")
                    status = request.GET.get("status", "all")
                    order = request.GET.get("order", "oldest_first")
                    if status not in ("all", "unclaimed", "claimed") or order not in (
                        "oldest_first",
                        "newest_first",
                    ):
                        raise ValueError("Invalid filters.")
                    itemFilter = (
                        uuid.UUID(request.GET["item_id"])
                        if request.GET.get("item_id")
                        else None
                    )
                    return _response(
                        QueueItemsResponse,
                        get_item_list(
                            queue,
                            access,
                            pageNumber=parse_page_number(request.GET),
                            status=status,
                            order=order,
                            itemId=itemFilter,
                        ),
                    )
                if request.GET:
                    raise ValueError("This endpoint does not accept filters.")
                if action == "item":
                    return _response(
                        QueueItemDetailsResponse,
                        build_item_payload(
                            QueueItem.objects.get(queue=queue, pk=itemId),
                            includeData=True,
                        ),
                    )
                return _response(
                    QueueDetailsResponse, {"queue": build_queue_payload(queue, access)}
                )
            if request.GET:
                raise ValueError("POST endpoints do not accept query parameters.")
            access = lock_session_write_access(
                membership.user_id,
                membership.organization_id,
                AccessChannel.SESSION,
                request.session.get(HASH_SESSION_KEY, ""),
                request.session.get_expiry_date(),
            )
            schema = (
                QueueCreationRequest
                if action == "list"
                else QueueDetailsRequest
                if action == "details"
                else QueueDeletionRequest
                if action == "delete_queue"
                else _MUTATION_SCHEMA[action]
            )
            payload = parse_json_request(
                request, schema, maxBodyBytes=MAX_QUEUE_RESPONSE_BYTES
            )
            if isinstance(payload, JsonResponse):
                return payload
            if action in ("list", "details"):
                assert isinstance(payload, QueueDetailsRequest)
                queue = save_queue(
                    access,
                    name=payload.name,
                    notes=payload.notes,
                    departmentId=payload.department_id
                    if isinstance(payload, QueueCreationRequest)
                    else None,
                    queueId=queueId,
                )
                return _response(
                    QueueDetailsResponse,
                    {"queue": build_queue_payload(queue, access)},
                    201 if action == "list" else 200,
                )
            if action == "delete_queue":
                assert queueId is not None
                delete_queue(access, queueId)
                return JsonResponse({"message": "Queue deleted."})
            assert isinstance(payload, QueueMutationRequest)
            if isinstance(payload, QueueDeleteItemsRequest) and payload.item_ids is None:
                raise ValueError("Select explicit item IDs in the browser.")
            return _response(
                QueueMutationResponse,
                mutate_items(access, action, payload, queueId=queueId),
            )
    except _HANDLED_ERRORS as e:
        return _error(e)


@csrf_exempt
@never_cache
@sensitive_variables()
def public_queue_request(request: HttpRequest, *, action: str) -> HttpResponse:
    """Bearer-only endpoints never derive identity from cookies or a submitted organization."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        retryAfter = reserve_api_key_authentication_request(
            request.META.get("REMOTE_ADDR", "")
        )
        if retryAfter:
            return build_rate_limited_response(retryAfter)
        authentication = authenticate_api_key(request.headers.get("Authorization", ""))
        if request.GET:
            raise ValueError("Use the JSON request body.")
        payload = parse_json_request(
            request,
            QueueQueryRequest if action == "query" else _MUTATION_SCHEMA[action],
            maxBodyBytes=MAX_QUEUE_RESPONSE_BYTES,
        )
        if isinstance(payload, JsonResponse):
            return payload
        with transaction.atomic():
            access = lock_api_key_write_access(authentication)
            if action == "query":
                assert isinstance(payload, QueueQueryRequest)
                queue = resolve_queue_path(access, payload.queue_path)
                return _response(QueueQueryResponse, query_items(queue, payload))
            assert isinstance(payload, QueueMutationRequest)
            return _response(
                QueueMutationResponse,
                mutate_items(access, action, payload, apiKeyId=authentication.apiKeyId),
            )
    except _HANDLED_ERRORS as e:
        return _error(e)
