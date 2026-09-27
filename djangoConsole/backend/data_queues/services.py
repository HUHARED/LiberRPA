# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import math
import uuid
from datetime import timedelta
from typing import TypedDict, cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from console_project.config import LimitsConfig
from console_project.contracts import JsonValue
from operations.audit import get_audit_snapshot, record_audit
from organizations.models import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import (
    QueueClaimRequest,
    QueueDeleteItemsRequest,
    QueueMutationRequest,
    QueueQueryRequest,
    QueueResetRequest,
    QueueUploadRequest,
)
from .models import DataQueue, QueueItem, QueueReceipt
from .queries import (
    build_item_payload,
    get_queue_query,
    normalize_queue_path,
    resolve_queue_path,
    select_items,
)

MAX_QUEUE_RESPONSE_BYTES = 2 * 1024 * 1024


class QueueMutationResult(TypedDict):
    request_id: str
    accepted_at: str
    item_ids: list[str]
    missing_ids: list[str]
    skipped_ids: list[str]
    items: list[dict[str, JsonValue]]
    deduplicated: bool


class QueueOperationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def encoded_size(payload: object) -> int:
    return len(
        json.dumps(
            payload,
            cls=DjangoJSONEncoder,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def validate_json_value(value: JsonValue, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("JSON must not exceed 64 levels of nesting.")
    if isinstance(value, (int, float)) and (
        not math.isfinite(value) or (value == int(value) and abs(value) > 2**53 - 1)
    ):
        raise ValueError("Use finite numbers and integers within the safe integer range.")
    if isinstance(value, dict):
        for key, child in value.items():
            key.encode("utf-8")
            validate_json_value(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            validate_json_value(child, depth + 1)
    elif isinstance(value, str):
        value.encode("utf-8")


def save_queue(
    access: OrganizationAccessContext,
    *,
    name: str,
    notes: str,
    departmentId: uuid.UUID | None = None,
    queueId: uuid.UUID | None = None,
) -> DataQueue:
    """The caller holds organization/account locks until this transaction commits."""
    if queueId is None:
        department = get_authorized_departments(
            access, requiredRole=DepartmentRole.DEVELOPER
        ).get(pk=departmentId)
        limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
        if (
            DataQueue.objects.filter(department__organization=access.organization).count()
            >= limits.maxDataQueuesPerOrganization
        ):
            raise QueueOperationError(
                "queue_count_limit", "This organization has reached its queue limit."
            )
        queue = DataQueue(department=department)
        before = {}
    else:
        queue = get_queue_query(access).get(pk=queueId)
        get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER).get(
            pk=queue.department_id
        )
        before = get_audit_snapshot(queue)
    queue.name = name
    queue.notes = notes
    queue.full_clean()
    queue.updated_at = timezone.now()
    queue.save()
    record_audit(
        "data_queue.create" if queueId is None else "data_queue.update",
        actorId=access.actorId,
        target=queue,
        organization=access.organization,
        channel=access.channel,
        before=before,
    )
    return get_queue_query(access).get(pk=queue.pk)


def delete_queue(access: OrganizationAccessContext, queueId: uuid.UUID) -> None:
    queue = get_queue_query(access).get(pk=queueId)
    get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER).get(
        pk=queue.department_id
    )
    record_audit(
        "data_queue.delete",
        actorId=access.actorId,
        target=queue,
        organization=access.organization,
        channel=access.channel,
        metadata={"item_count": QueueItem.objects.filter(queue=queue).count()},
    )
    queue.delete()


def query_items(queue: DataQueue, payload: QueueQueryRequest) -> dict[str, object]:
    query = select_items(
        queue, status=payload.status, order=payload.order, itemId=payload.item_id
    )
    if payload.after_sequence is not None:
        query = query.filter(**{
            "sequence__gt"
            if payload.order == "oldest_first"
            else "sequence__lt": payload.after_sequence
        })
    result: dict[str, object] = {"items": [], "next_sequence": None}
    rows = cast(list[dict[str, object]], result["items"])
    candidates = list(query[: payload.count + 1])
    for item in candidates[: payload.count]:
        entry = build_item_payload(item, includeData=True)
        proposed = {"items": [*rows, entry], "next_sequence": item.sequence}
        if encoded_size(proposed) > MAX_QUEUE_RESPONSE_BYTES:
            if not rows:
                raise QueueOperationError(
                    "queue_response_too_large", "This item cannot fit in one response."
                )
            break
        rows.append(entry)
    if len(candidates) > len(rows):
        result["next_sequence"] = rows[-1]["sequence"]
    return result


@sensitive_variables()
def mutate_items(
    access: OrganizationAccessContext,
    operation: str,
    payload: QueueMutationRequest,
    *,
    queueId: uuid.UUID | None = None,
    apiKeyId: uuid.UUID | None = None,
) -> dict[str, object]:
    """Serialize selection, quotas, effects, receipts and audit under the shared organization lock."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    normalized = payload.model_dump(mode="json", exclude={"request_id"})
    if queueId is None:
        if payload.queue_path is None:
            raise ValueError("queue_path is required.")
        normalized["queue_path"] = normalize_queue_path(payload.queue_path).lower()
    elif payload.queue_path is not None:
        raise ValueError("The browser endpoint identifies its queue in the URL.")
    normalized["queue_id"] = str(queueId) if queueId else None
    digest = hashlib.sha256(
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    receipts = QueueReceipt.objects.filter(organization=access.organization)
    result: QueueMutationResult
    receipt = receipts.filter(
        actor_id=access.actorId, operation=operation, request_id=payload.request_id
    ).first()
    if receipt is not None:
        get_authorized_departments(access, requiredRole=DepartmentRole.OPERATOR).get(
            pk=receipt.department_id
        )
        if receipt.request_digest != digest:
            raise QueueOperationError(
                "idempotency_conflict",
                "This request_id was already used with different input.",
            )
        result = cast(QueueMutationResult, {**receipt.result, "deduplicated": True})
        if operation == "claim":
            dataById = {
                str(item.id): json.loads(item.data_json)
                for item in QueueItem.objects.filter(
                    queue_id=receipt.queue_id, pk__in=result["item_ids"]
                )
            }
            result["items"] = [
                {"id": itemId, "data": dataById[itemId]}
                for itemId in result["item_ids"]
                if itemId in dataById
            ]
            result["missing_ids"] = [
                itemId for itemId in result["item_ids"] if itemId not in dataById
            ]
        return cast(dict[str, object], result)
    queue = (
        get_queue_query(access).get(pk=queueId)
        if queueId
        else resolve_queue_path(access, cast(str, payload.queue_path))
    )
    receipts.filter(
        created_at__lt=timezone.now() - timedelta(days=limits.queueReceiptRetentionDays)
    ).delete()
    if receipts.count() >= limits.maxQueueReceiptsPerOrganization:
        raise QueueOperationError(
            "queue_receipt_limit",
            "The queue request history is full. Retry after old receipts expire.",
        )
    now = timezone.now()
    result = {
        "request_id": str(payload.request_id),
        "accepted_at": now.isoformat(),
        "item_ids": [],
        "missing_ids": [],
        "skipped_ids": [],
        "items": [],
        "deduplicated": False,
    }
    actorName = str(User.objects.get(pk=access.actorId))[:254]
    if operation == "upload":
        assert isinstance(payload, QueueUploadRequest)
        listJson = []
        for index, value in enumerate(payload.items):
            try:
                validate_json_value(value)
                serialized = json.dumps(
                    value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                )
                if len(serialized.encode("utf-8")) > limits.maxQueueItemBytes:
                    raise ValueError("The item exceeds the configured byte limit.")
            except (ValueError, RecursionError, OverflowError) as e:
                raise ValidationError({"items": f"Item {index + 1}: {e}"}) from None
            listJson.append(serialized)
        items = QueueItem.objects.filter(
            queue__department__organization=access.organization
        )
        if (
            items.count() + len(listJson) > limits.maxQueueItemsPerOrganization
            or (items.aggregate(total=Sum("size_bytes"))["total"] or 0)
            + sum(len(value.encode("utf-8")) for value in listJson)
            > limits.maxQueueDataBytesPerOrganization
        ):
            raise QueueOperationError(
                "queue_capacity_limit",
                "This batch exceeds the organization's queue item or byte limit.",
            )
        created = QueueItem.objects.bulk_create([
            QueueItem(
                queue=queue,
                sequence=queue.next_sequence + index,
                data_json=value,
                size_bytes=len(value.encode("utf-8")),
                uploaded_by_id=access.actorId,
                uploaded_by_name=actorName,
                uploaded_at=now,
            )
            for index, value in enumerate(listJson)
        ])
        queue.next_sequence += len(created)
        queue.save(update_fields=["next_sequence"])
        result["item_ids"] = [str(item.id) for item in created]
    elif operation == "claim":
        assert isinstance(payload, QueueClaimRequest)
        for item in select_items(
            queue, status=payload.status, order=payload.order, itemId=payload.item_id
        )[: payload.count]:
            proposed: QueueMutationResult = {
                **result,
                "items": [
                    *result["items"],
                    {"id": str(item.id), "data": json.loads(item.data_json)},
                ],
                "item_ids": [*result["item_ids"], str(item.id)],
            }
            if encoded_size(proposed) > MAX_QUEUE_RESPONSE_BYTES - 128:
                if not result["item_ids"]:
                    raise QueueOperationError(
                        "queue_response_too_large",
                        "This item cannot fit in one response.",
                    )
                break
            result = proposed
        QueueItem.objects.filter(queue=queue, pk__in=result["item_ids"]).update(
            status=QueueItem.Status.CLAIMED,
            last_claimed_by_id=access.actorId,
            last_claimed_by_name=actorName,
            last_claimed_at=now,
        )
    else:
        assert isinstance(payload, (QueueResetRequest, QueueDeleteItemsRequest))
        if payload.item_ids is not None:
            ids = list(dict.fromkeys(str(itemId) for itemId in payload.item_ids))
            itemsById = {
                str(item.id): item
                for item in QueueItem.objects.filter(queue=queue, pk__in=ids).defer(
                    "data_json"
                )
            }
            result["missing_ids"] = [itemId for itemId in ids if itemId not in itemsById]
            chosen = [itemsById[itemId] for itemId in ids if itemId in itemsById]
        else:
            assert isinstance(payload, QueueDeleteItemsRequest)
            chosen = list(
                select_items(queue, status=payload.status, order=payload.order).defer(
                    "data_json"
                )[: payload.count]
            )
        result["item_ids"] = [
            str(item.id)
            for item in chosen
            if operation != "reset" or item.status == QueueItem.Status.CLAIMED
        ]
        if operation == "reset":
            result["skipped_ids"] = [
                str(item.id)
                for item in chosen
                if item.status == QueueItem.Status.UNCLAIMED
            ]
            QueueItem.objects.filter(queue=queue, pk__in=result["item_ids"]).update(
                status=QueueItem.Status.UNCLAIMED
            )
        elif operation == "delete_items":
            QueueItem.objects.filter(queue=queue, pk__in=result["item_ids"]).delete()
        else:
            raise ValueError("Unsupported queue operation.")
    QueueReceipt.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        operation=operation,
        request_id=payload.request_id,
        request_digest=digest,
        queue_id=queue.pk,
        department_id=queue.department_id,
        result={**result, "items": []},
        created_at=now,
    )
    metadata: dict[str, object] = {
        "request_id": str(payload.request_id),
        "item_ids": result["item_ids"],
        "item_count": len(result["item_ids"]),
    }
    if apiKeyId is not None:
        metadata["api_key_id"] = str(apiKeyId)
    record_audit(
        f"data_queue.{operation}",
        actorId=access.actorId,
        target=queue,
        organization=access.organization,
        channel=access.channel,
        metadata=metadata,
    )
    return cast(dict[str, object], result)
