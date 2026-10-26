# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods, require_GET, require_POST

from console_project.contracts import MessageResponse
from console_project.http import parse_page_number
from organizations.http import (
    lock_request_write_access,
    parse_department_resource_filters,
)
from organizations.models import Membership
from organizations.permissions import AccessChannel, build_organization_access
from organizations.rate_limits import RequestBudget, check_request_budget, request_budget

from .contracts import (
    QueueItemFilterStatus,
    QueueItemOrder,
    QueueDetailsRequest,
    QueueCreationRequest,
    QueueDeletionRequest,
    QueueUploadRequest,
    QueueResetRequest,
    QueueDeleteItemsRequest,
    QueueDetailsResponse,
)
from .models import QueueItem
from .queries import (
    get_queue_query,
    build_queue_payloads,
    get_queue_list,
    build_item_details,
    get_item_list,
)
from .services import (
    create_queue,
    update_queue,
    delete_queue,
    upload_items,
    reset_items,
    delete_items,
)
from .http import (
    QueueRequestError,
    session_queue_view,
    parse_queue_request,
    parse_item_request,
    build_queue_response,
)


@require_http_methods(["GET", "POST"])
@session_queue_view
def list_or_create_queues(request: HttpRequest, membership: Membership) -> HttpResponse:
    if request.method == "GET":
        try:
            filters = parse_department_resource_filters(request.GET)
        except ValueError:
            raise QueueRequestError(
                "Use one positive page, one name, and department UUIDs.",
            ) from None
        access = build_organization_access(membership, channel=AccessChannel.SESSION)
        return build_queue_response(get_queue_list(access, **filters))
    payload = parse_queue_request(request, QueueCreationRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        queue = create_queue(
            access,
            departmentId=payload.department_id,
            name=payload.name,
            notes=payload.notes,
        )
        return build_queue_response(
            QueueDetailsResponse(queue=build_queue_payloads([queue], access)[0]),
            statusCode=201,
        )


@require_http_methods(["GET", "POST"])
@session_queue_view
def get_or_update_queue(
    request: HttpRequest,
    membership: Membership,
    queueId: uuid.UUID,
) -> HttpResponse:
    if request.method == "GET":
        if request.GET:
            raise QueueRequestError("This endpoint does not accept filters.")
        access = build_organization_access(membership, channel=AccessChannel.SESSION)
        queue = get_queue_query(access, includeCounts=True).get(pk=queueId)
        return build_queue_response(
            QueueDetailsResponse(queue=build_queue_payloads([queue], access)[0]),
        )
    payload = parse_queue_request(request, QueueDetailsRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        queue = update_queue(access, queueId, name=payload.name, notes=payload.notes)
        return build_queue_response(
            QueueDetailsResponse(queue=build_queue_payloads([queue], access)[0]),
        )


@require_POST
@session_queue_view
def delete_queue_view(
    request: HttpRequest,
    membership: Membership,
    queueId: uuid.UUID,
) -> HttpResponse:
    payload = parse_queue_request(request, QueueDeletionRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        delete_queue(access, queueId)
        return build_queue_response(MessageResponse(message="Queue deleted."))


@require_GET
@session_queue_view
def list_queue_items(
    request: HttpRequest,
    membership: Membership,
    queueId: uuid.UUID,
) -> HttpResponse:
    try:
        if set(request.GET) - {"page", "status", "order", "item_id"} or any(
            len(request.GET.getlist(strKey)) != 1 for strKey in request.GET
        ):
            raise ValueError
        status = QueueItemFilterStatus(
            request.GET.get("status", QueueItemFilterStatus.ALL)
        )
        order = QueueItemOrder(request.GET.get("order", QueueItemOrder.OLDEST_FIRST))
        itemId = uuid.UUID(request.GET["item_id"]) if request.GET.get("item_id") else None
        intPageNumber = parse_page_number(request.GET)
    except ValueError:
        raise QueueRequestError(
            "Use supported fields, valid UUIDs, and valid queue filters.",
        ) from None
    access = build_organization_access(membership, channel=AccessChannel.SESSION)
    queue = get_queue_query(access, includeCounts=True).get(pk=queueId)
    return build_queue_response(
        get_item_list(
            queue,
            access,
            pageNumber=intPageNumber,
            status=status,
            order=order,
            itemId=itemId,
        ),
    )


@require_GET
@session_queue_view
def get_queue_item(
    request: HttpRequest,
    membership: Membership,
    queueId: uuid.UUID,
    itemId: uuid.UUID,
) -> HttpResponse:
    if request.GET:
        raise QueueRequestError("This endpoint does not accept filters.")
    access = build_organization_access(membership, channel=AccessChannel.SESSION)
    queue = get_queue_query(access).get(pk=queueId)
    return build_queue_response(
        build_item_details(QueueItem.objects.get(queue=queue, pk=itemId)),
    )


@require_POST
@session_queue_view
@request_budget(RequestBudget.DEFERRED)
def upload_queue_items(
    request: HttpRequest,
    membership: Membership,
    queueId: uuid.UUID,
) -> HttpResponse:
    parsed = parse_item_request(request, QueueUploadRequest, queueId=queueId)
    if isinstance(parsed, JsonResponse):
        return parsed
    queueReference, payload = parsed
    check_request_budget(
        request,
        membership.organization,
        budget=RequestBudget.WRITE,
        cost=len(payload.items),
    )
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        return build_queue_response(upload_items(access, queueReference, payload))


@require_POST
@session_queue_view
@request_budget(RequestBudget.DEFERRED)
def reset_queue_items(
    request: HttpRequest,
    membership: Membership,
    queueId: uuid.UUID,
) -> HttpResponse:
    parsed = parse_item_request(request, QueueResetRequest, queueId=queueId)
    if isinstance(parsed, JsonResponse):
        return parsed
    queueReference, payload = parsed
    check_request_budget(
        request,
        membership.organization,
        budget=RequestBudget.WRITE,
        cost=len(set(payload.item_ids)),
    )
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        return build_queue_response(reset_items(access, queueReference, payload))


@require_POST
@session_queue_view
@request_budget(RequestBudget.DEFERRED)
def delete_queue_items(
    request: HttpRequest,
    membership: Membership,
    queueId: uuid.UUID,
) -> HttpResponse:
    parsed = parse_item_request(request, QueueDeleteItemsRequest, queueId=queueId)
    if isinstance(parsed, JsonResponse):
        return parsed
    queueReference, payload = parsed
    if payload.item_ids is None:
        raise QueueRequestError("Select explicit item IDs in the browser.")
    check_request_budget(
        request,
        membership.organization,
        budget=RequestBudget.WRITE,
        cost=len(set(payload.item_ids)),
    )
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        return build_queue_response(delete_items(access, queueReference, payload))
