# FileName: public_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from accounts.resource_authentication import (
    ResourceAuthenticationContext,
    lock_resource_write_access,
)
from organizations.validators import parse_resource_path

from .contracts import (
    QueueUploadRequest,
    QueueQueryRequest,
    QueueClaimRequest,
    QueueResetRequest,
    QueueDeleteItemsRequest,
)
from .queries import resolve_queue_path, query_items
from .services import upload_items, claim_items, reset_items, delete_items
from .http import (
    api_queue_view,
    parse_queue_request,
    parse_item_request,
    build_queue_response,
)


@require_POST
@api_queue_view
def query_queue_items(
    request: HttpRequest,
    authentication: ResourceAuthenticationContext,
) -> HttpResponse:
    payload = parse_queue_request(request, QueueQueryRequest)
    if isinstance(payload, JsonResponse):
        return payload
    queue = resolve_queue_path(
        authentication.access,
        parse_resource_path(payload.queue_path),
    )
    return build_queue_response(query_items(queue, payload))


@require_POST
@api_queue_view
def upload_queue_items(
    request: HttpRequest,
    authentication: ResourceAuthenticationContext,
) -> HttpResponse:
    parsed = parse_item_request(request, QueueUploadRequest)
    if isinstance(parsed, JsonResponse):
        return parsed
    queueReference, payload = parsed
    with transaction.atomic():
        access = lock_resource_write_access(authentication)
        return build_queue_response(
            upload_items(
                access, queueReference, payload, apiKeyId=authentication.apiKeyId
            ),
        )


@require_POST
@api_queue_view
def claim_queue_items(
    request: HttpRequest,
    authentication: ResourceAuthenticationContext,
) -> HttpResponse:
    parsed = parse_item_request(request, QueueClaimRequest)
    if isinstance(parsed, JsonResponse):
        return parsed
    queueReference, payload = parsed
    with transaction.atomic():
        access = lock_resource_write_access(authentication)
        return build_queue_response(
            claim_items(
                access, queueReference, payload, apiKeyId=authentication.apiKeyId
            ),
        )


@require_POST
@api_queue_view
def reset_queue_items(
    request: HttpRequest,
    authentication: ResourceAuthenticationContext,
) -> HttpResponse:
    parsed = parse_item_request(request, QueueResetRequest)
    if isinstance(parsed, JsonResponse):
        return parsed
    queueReference, payload = parsed
    with transaction.atomic():
        access = lock_resource_write_access(authentication)
        return build_queue_response(
            reset_items(
                access, queueReference, payload, apiKeyId=authentication.apiKeyId
            ),
        )


@require_POST
@api_queue_view
def delete_queue_items(
    request: HttpRequest,
    authentication: ResourceAuthenticationContext,
) -> HttpResponse:
    parsed = parse_item_request(request, QueueDeleteItemsRequest)
    if isinstance(parsed, JsonResponse):
        return parsed
    queueReference, payload = parsed
    with transaction.atomic():
        access = lock_resource_write_access(authentication)
        return build_queue_response(
            delete_items(
                access, queueReference, payload, apiKeyId=authentication.apiKeyId
            ),
        )
