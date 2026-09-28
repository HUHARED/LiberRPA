# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from collections.abc import Generator
from contextlib import closing
from typing import cast

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet
from django.db.models.functions import Substr

from organizations.department_queries import (
    get_department_tree,
    resolve_department_path,
    get_department_path,
)
from organizations.models import DepartmentRole
from organizations.validators import get_path_name_key
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import (
    MAX_QUEUE_RESPONSE_BYTES,
    QueueQueryRequest,
    QueueDepartmentResponse,
    QueueEntryResponse,
    QueueListResponse,
    QueueItemResponse,
    QueueItemDetailsResponse,
    QueueItemsResponse,
    QueueQueryResponse,
)
from .models import DataQueue, QueueItem


def get_queue_query(
    access: OrganizationAccessContext,
    *,
    requiredRole: DepartmentRole = DepartmentRole.OPERATOR,
    includeCounts: bool = False,
) -> QuerySet[DataQueue]:
    query = DataQueue.objects.filter(
        department__in=get_authorized_departments(access, requiredRole=requiredRole)
    )
    if includeCounts:
        query = query.annotate(
            unclaimed_count=Count(
                "items",
                filter=Q(items__status=QueueItem.Status.UNCLAIMED),
            ),
            claimed_count=Count(
                "items", filter=Q(items__status=QueueItem.Status.CLAIMED)
            ),
        )
    return query


def resolve_queue_path(
    access: OrganizationAccessContext, normalizedPath: str
) -> DataQueue:
    """Resolve a path already normalized at the request boundary."""
    pathParts = tuple(normalizedPath.split("/")[1:])
    departmentsById = get_department_tree(access.organization.pk)
    department = resolve_department_path(pathParts[:-1], departmentsById)
    # Resolving a department path never grants access to its queues.
    return get_queue_query(access).get(
        department_id=department.pk,
        name_key=get_path_name_key(pathParts[-1]),
    )


def build_queue_payloads(
    queues: list[DataQueue], access: OrganizationAccessContext
) -> list[QueueEntryResponse]:
    """Build one page using one department tree and one management-permission set."""
    if not queues:
        return []
    departmentsById = get_department_tree(access.organization.pk)
    managedDepartmentIds = (
        set(
            get_authorized_departments(
                access, requiredRole=DepartmentRole.DEVELOPER
            ).values_list("id", flat=True)
        )
        if access.channel == AccessChannel.SESSION
        else set()
    )
    listPayload: list[QueueEntryResponse] = []
    for queue in queues:
        departmentPath = get_department_path(
            departmentsById[queue.department_id], departmentsById
        )
        listPayload.append(
            QueueEntryResponse(
                id=queue.pk,
                name=queue.name,
                department=QueueDepartmentResponse(
                    id=queue.department_id, path=departmentPath
                ),
                path=f"/{departmentPath}/{queue.name}",
                notes=queue.notes,
                unclaimed_count=queue.unclaimed_count,
                claimed_count=queue.claimed_count,
                can_manage=queue.department_id in managedDepartmentIds,
                created_at=queue.created_at,
                updated_at=queue.updated_at,
            )
        )
    return listPayload


def get_queue_list(
    access: OrganizationAccessContext,
    *,
    pageNumber: int = 1,
    departmentIds: tuple[uuid.UUID, ...] = (),
    name: str = "",
) -> QueueListResponse:
    query = get_queue_query(access, includeCounts=True)
    if departmentIds:
        query = query.filter(department_id__in=departmentIds)
    if name:
        query = query.filter(name_key__contains=get_path_name_key(name))
    page = Paginator(query.order_by("name_key", "id"), 50).page(pageNumber)
    return QueueListResponse(
        queues=build_queue_payloads(list(page.object_list), access),
        page=page.number,
        page_size=50,
        total_count=page.paginator.count,
        total_pages=page.paginator.num_pages,
    )


def select_items(
    queue: DataQueue,
    *,
    status: str = "all",
    order: str = "oldest_first",
    itemId: uuid.UUID | None = None,
) -> QuerySet[QueueItem]:
    query = QueueItem.objects.filter(queue=queue)
    if status != "all":
        query = query.filter(status=status)
    if itemId is not None:
        query = query.filter(pk=itemId)
    return query.order_by("sequence" if order == "oldest_first" else "-sequence")


def _build_item_metadata(item: QueueItem, summary: str) -> dict[str, object]:
    return {
        "id": item.id,
        "sequence": item.sequence,
        "status": item.status,
        "data_summary": summary[:160] + ("…" if len(summary) > 160 else ""),
        "uploaded_by_id": item.uploaded_by_id,
        "uploaded_by_name": item.uploaded_by_name,
        "uploaded_at": item.uploaded_at,
        "last_claimed_by_id": item.last_claimed_by_id,
        "last_claimed_by_name": item.last_claimed_by_name,
        "last_claimed_at": item.last_claimed_at,
    }


def build_item_details(item: QueueItem) -> QueueItemDetailsResponse:
    return QueueItemDetailsResponse.model_validate({
        **_build_item_metadata(item, item.data_json[:161]),
        "data": json.loads(item.data_json),
    })


def get_item_list(
    queue: DataQueue,
    access: OrganizationAccessContext,
    *,
    pageNumber: int = 1,
    status: str = "all",
    order: str = "oldest_first",
    itemId: uuid.UUID | None = None,
) -> QueueItemsResponse:
    query = (
        select_items(queue, status=status, order=order, itemId=itemId)
        .annotate(summary=Substr("data_json", 1, 161))
        .defer("data_json")
    )
    page = Paginator(query, 50).page(pageNumber)
    return QueueItemsResponse(
        queue=build_queue_payloads([queue], access)[0],
        items=[
            QueueItemResponse.model_validate(_build_item_metadata(item, item.summary))
            for item in page
        ],
        page=page.number,
        page_size=50,
        total_count=page.paginator.count,
        total_pages=page.paginator.num_pages,
    )


def query_items(queue: DataQueue, payload: QueueQueryRequest) -> QueueQueryResponse:
    query = select_items(
        queue, status=payload.status, order=payload.order, itemId=payload.item_id
    )
    if payload.after_sequence is not None:
        lookup = "sequence__gt" if payload.order == "oldest_first" else "sequence__lt"
        query = query.filter(**{lookup: payload.after_sequence})
    result = QueueQueryResponse(items=[], next_sequence=None)
    responseBytes = len(result.model_dump_json().encode("utf-8"))
    # Read one body at a time and close the cursor even when the byte budget stops the loop.
    # NOTE: Django's iterator() returns a generator; django-stubs declares Iterator.
    with closing(
        cast(
            Generator[QueueItem],
            query[: payload.count + 1].iterator(chunk_size=1),
        )
    ) as candidates:
        for item in candidates:
            if len(result.items) == payload.count:
                return result.model_copy(
                    update={"next_sequence": result.items[-1].sequence},
                )
            entry = build_item_details(item)
            entryBytes = len(entry.model_dump_json().encode("utf-8")) + bool(result.items)
            cursorBytes = max(0, len(str(item.sequence)) - len("null"))
            if responseBytes + entryBytes + cursorBytes > MAX_QUEUE_RESPONSE_BYTES:
                if not result.items:
                    raise ValidationError(
                        "This queue item cannot fit in one response.",
                        code="queue_response_too_large",
                    )
                return result.model_copy(
                    update={"next_sequence": result.items[-1].sequence},
                )
            result.items.append(entry)
            responseBytes += entryBytes
    return result
