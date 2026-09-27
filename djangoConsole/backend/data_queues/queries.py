# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid

from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet
from django.db.models.functions import Lower, Substr

from organizations.department_queries import get_department_path
from organizations.models import Department, DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
)
from organizations.validators import validate_path_segment

from .models import DataQueue, QueueItem


def get_queue_query(access: OrganizationAccessContext) -> QuerySet[DataQueue]:
    return DataQueue.objects.filter(
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        )
    ).annotate(
        unclaimed_count=Count("items", filter=Q(items__status="unclaimed")),
        claimed_count=Count("items", filter=Q(items__status="claimed")),
    )


def normalize_queue_path(path: str) -> str:
    listPart = path.replace("\\", "/").removeprefix("/").split("/")
    if len(listPart) < 2 or len(listPart) > 65:
        raise ValueError("Use a full department path and queue name.")
    for part in listPart:
        validate_path_segment(part)
        if len(part) > 128:
            raise ValueError("Path segments must not exceed 128 characters.")
    return "/" + "/".join(listPart)


def resolve_queue_path(access: OrganizationAccessContext, path: str) -> DataQueue:
    listPart = normalize_queue_path(path).split("/")[1:]
    departmentId = None
    for part in listPart[:-1]:
        departmentId = Department.objects.get(
            organization=access.organization,
            deleted_at__isnull=True,
            parent_id=departmentId,
            name__iexact=part,
        ).pk
    return get_queue_query(access).get(
        department_id=departmentId, name__iexact=listPart[-1]
    )


def build_queue_payload(
    queue: DataQueue, access: OrganizationAccessContext
) -> dict[str, object]:
    departments = {
        department.id: department
        for department in Department.objects.filter(
            organization=access.organization, deleted_at__isnull=True
        )
    }
    path = get_department_path(departments[queue.department_id], departments)
    boolManage = (
        access.channel == AccessChannel.SESSION
        and get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER)
        .filter(pk=queue.department_id)
        .exists()
    )
    return {
        "id": queue.pk,
        "name": queue.name,
        "department": {"id": queue.department_id, "path": path},
        "path": f"/{path}/{queue.name}",
        "notes": queue.notes,
        "unclaimed_count": queue.unclaimed_count,
        "claimed_count": queue.claimed_count,
        "can_manage": boolManage,
        "created_at": queue.created_at,
        "updated_at": queue.updated_at,
    }


def get_queue_list(
    access: OrganizationAccessContext,
    *,
    pageNumber: int = 1,
    departmentIds: tuple[uuid.UUID, ...] = (),
    name: str = "",
) -> dict[str, object]:
    query = get_queue_query(access)
    if departmentIds:
        query = query.filter(department_id__in=departmentIds)
    if name:
        query = query.filter(name__icontains=name)
    page = Paginator(query.order_by(Lower("name"), "id"), 50).page(pageNumber)
    return {
        "queues": [build_queue_payload(queue, access) for queue in page],
        "page": page.number,
        "page_size": 50,
        "total_count": page.paginator.count,
        "total_pages": page.paginator.num_pages,
    }


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


def build_item_payload(
    item: QueueItem, *, includeData: bool = False
) -> dict[str, object]:
    summary = item.data_json[:161] if includeData else item.summary
    payload = {
        field: getattr(item, field)
        for field in (
            "id",
            "sequence",
            "status",
            "uploaded_by_id",
            "uploaded_by_name",
            "uploaded_at",
            "last_claimed_by_id",
            "last_claimed_by_name",
            "last_claimed_at",
        )
    }
    payload["data_summary"] = summary[:160] + ("…" if len(summary) > 160 else "")
    if includeData:
        payload["data"] = json.loads(item.data_json)
    return payload


def get_item_list(
    queue: DataQueue,
    access: OrganizationAccessContext,
    *,
    pageNumber: int = 1,
    status: str = "all",
    order: str = "oldest_first",
    itemId: uuid.UUID | None = None,
) -> dict[str, object]:
    query = (
        select_items(queue, status=status, order=order, itemId=itemId)
        .annotate(summary=Substr("data_json", 1, 161))
        .defer("data_json")
    )
    page = Paginator(query, 50).page(pageNumber)
    return {
        "queue": build_queue_payload(queue, access),
        "items": [build_item_payload(item) for item in page],
        "page": page.number,
        "page_size": 50,
        "total_count": page.paginator.count,
        "total_pages": page.paginator.num_pages,
    }
