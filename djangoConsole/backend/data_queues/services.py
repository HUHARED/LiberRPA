# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import uuid
from collections.abc import Callable, Generator
from contextlib import closing
from datetime import timedelta
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from console_project.validators import validate_json_value
from operations.audit import get_audit_snapshot, record_audit
from organizations.models import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import (
    MAX_QUEUE_RESPONSE_BYTES,
    QueueMutationRequest,
    QueueUploadRequest,
    QueueClaimRequest,
    QueueResetRequest,
    QueueDeleteItemsRequest,
    QueueClaimedItemResponse,
    QueueMutationResponse,
)
from .models import DataQueue, QueueItem, QueueReceipt
from .queries import get_queue_query, resolve_queue_path, select_items


class QueueOperationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def create_queue(
    access: OrganizationAccessContext, *, departmentId: uuid.UUID, name: str, notes: str
) -> DataQueue:
    """The caller keeps organization/account locks through the response and commit."""
    department = get_authorized_departments(
        access,
        requiredRole=DepartmentRole.DEVELOPER,
    ).get(pk=departmentId)
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if (
        DataQueue.objects.filter(
            department__organization=access.organization,
        ).count()
        >= limits.maxDataQueuesPerOrganization
    ):
        raise QueueOperationError(
            "queue_count_limit",
            "This organization has reached its queue limit.",
        )
    queue = DataQueue(department=department, name=name, notes=notes)
    queue.full_clean()
    queue.save()
    record_audit(
        "data_queue.create",
        actorId=access.actorId,
        target=queue,
        organization=access.organization,
        channel=access.channel,
        before={},
    )
    queue.unclaimed_count = 0
    queue.claimed_count = 0
    return queue


def update_queue(
    access: OrganizationAccessContext, queueId: uuid.UUID, *, name: str, notes: str
) -> DataQueue:
    queue = get_queue_query(
        access,
        requiredRole=DepartmentRole.DEVELOPER,
        includeCounts=True,
    ).get(pk=queueId)
    before = get_audit_snapshot(queue)
    queue.name = name
    queue.notes = notes
    queue.full_clean()
    queue.updated_at = timezone.now()
    queue.save(update_fields=["name", "notes", "updated_at"])
    record_audit(
        "data_queue.update",
        actorId=access.actorId,
        target=queue,
        organization=access.organization,
        channel=access.channel,
        before=before,
    )
    return queue


def delete_queue(access: OrganizationAccessContext, queueId: uuid.UUID) -> None:
    queue = get_queue_query(access, requiredRole=DepartmentRole.DEVELOPER).get(pk=queueId)
    record_audit(
        "data_queue.delete",
        actorId=access.actorId,
        target=queue,
        organization=access.organization,
        channel=access.channel,
        metadata={"item_count": QueueItem.objects.filter(queue=queue).count()},
    )
    queue.delete()


@sensitive_variables()
def _mutate_items(
    access: OrganizationAccessContext,
    queueReference: uuid.UUID | str,
    payload: QueueMutationRequest,
    *,
    operation: str,
    applyChange: Callable[[DataQueue, QueueMutationResponse], None],
    apiKeyId: uuid.UUID | None,
) -> QueueMutationResponse:
    """Keep the item change, receipt and audit within the caller's organization/account write locks."""
    normalized = payload.model_dump(mode="json", exclude={"request_id", "queue_path"})
    normalized["queue_id"] = (
        str(queueReference) if isinstance(queueReference, uuid.UUID) else None
    )
    normalized["queue_path"] = (
        queueReference.lower() if isinstance(queueReference, str) else None
    )
    digest = hashlib.sha256(
        json.dumps(
            normalized,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    ).hexdigest()
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    now = timezone.now()
    cutoff = now - timedelta(days=limits.queueReceiptRetentionDays)
    receipts = QueueReceipt.objects.filter(organization=access.organization)
    receipt = receipts.filter(
        actor_id=access.actorId,
        operation=operation,
        request_id=payload.request_id,
    ).first()
    if receipt is not None:
        get_authorized_departments(
            access,
            requiredRole=DepartmentRole.OPERATOR,
        ).get(pk=receipt.department_id)
        if receipt.request_digest != digest:
            raise QueueOperationError(
                "idempotency_conflict",
                "This request_id was already used with different input.",
            )
        # JSONField stores UUIDs and datetimes as strings; parse them only at this persistence boundary.
        result = QueueMutationResponse.model_validate(
            receipt.result, strict=False
        ).model_copy(update={"deduplicated": True})
        if operation == "claim":
            dataById = dict(
                QueueItem.objects.filter(
                    queue_id=receipt.queue_id,
                    pk__in=result.item_ids,
                ).values_list("id", "data_json"),
            )
            result.items.extend(
                QueueClaimedItemResponse(id=itemId, data=json.loads(dataById[itemId]))
                for itemId in result.item_ids
                if itemId in dataById
            )
            result.missing_ids.extend(
                itemId for itemId in result.item_ids if itemId not in dataById
            )
        return result
    queue = (
        get_queue_query(access).get(pk=queueReference)
        if isinstance(queueReference, uuid.UUID)
        else resolve_queue_path(access, queueReference)
    )
    receipts.filter(created_at__lt=cutoff).delete()
    if receipts.count() >= limits.maxQueueReceiptsPerOrganization:
        raise QueueOperationError(
            "queue_receipt_limit",
            "The queue request history is full. Retry after old receipts expire.",
        )
    result = QueueMutationResponse(
        request_id=payload.request_id,
        accepted_at=now,
        item_ids=[],
        missing_ids=[],
        skipped_ids=[],
        items=[],
        deduplicated=False,
    )
    applyChange(queue, result)
    QueueReceipt.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        operation=operation,
        request_id=payload.request_id,
        request_digest=digest,
        queue_id=queue.pk,
        department_id=queue.department_id,
        result={**result.model_dump(mode="json", exclude={"items"}), "items": []},
        created_at=now,
    )
    metadata: dict[str, object] = {
        "request_id": str(payload.request_id),
        "item_ids": [str(itemId) for itemId in result.item_ids],
        "item_count": len(result.item_ids),
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
    return result


@sensitive_variables()
def upload_items(
    access: OrganizationAccessContext,
    queueReference: uuid.UUID | str,
    payload: QueueUploadRequest,
    *,
    apiKeyId: uuid.UUID | None = None,
) -> QueueMutationResponse:
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    serializedItems: list[tuple[str, int]] = []
    for index, value in enumerate(payload.items):
        try:
            validate_json_value(value)
            serialized = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            sizeBytes = len(serialized.encode("utf-8"))
        except (ValueError, RecursionError, OverflowError) as e:
            raise ValidationError({"items": f"Item {index + 1}: {e}"}) from None
        serializedItems.append((serialized, sizeBytes))

    def apply_upload(queue: DataQueue, result: QueueMutationResponse) -> None:
        for index, (_, sizeBytes) in enumerate(serializedItems):
            if sizeBytes > limits.maxQueueItemBytes:
                raise ValidationError({
                    "items": f"Item {index + 1}: The item exceeds the configured byte limit."
                })
        usage = QueueItem.objects.filter(
            queue__department__organization=access.organization
        ).aggregate(
            item_count=Count("id"),
            data_bytes=Sum("size_bytes", default=0),
        )
        if (
            usage["item_count"] + len(serializedItems)
            > limits.maxQueueItemsPerOrganization
            or usage["data_bytes"] + sum(sizeBytes for _, sizeBytes in serializedItems)
            > limits.maxQueueDataBytesPerOrganization
        ):
            raise QueueOperationError(
                "queue_capacity_limit",
                "This batch exceeds the organization's queue item or byte limit.",
            )
        actorName = str(access.actor)
        created = QueueItem.objects.bulk_create([
            QueueItem(
                queue=queue,
                sequence=queue.next_sequence + index,
                data_json=serialized,
                size_bytes=sizeBytes,
                uploaded_by_id=access.actorId,
                uploaded_by_name=actorName,
                uploaded_at=result.accepted_at,
            )
            for index, (serialized, sizeBytes) in enumerate(serializedItems)
        ])
        queue.next_sequence += len(created)
        queue.save(update_fields=["next_sequence"])
        result.item_ids.extend(item.id for item in created)

    return _mutate_items(
        access,
        queueReference,
        payload,
        operation="upload",
        applyChange=apply_upload,
        apiKeyId=apiKeyId,
    )


@sensitive_variables()
def claim_items(
    access: OrganizationAccessContext,
    queueReference: uuid.UUID | str,
    payload: QueueClaimRequest,
    *,
    apiKeyId: uuid.UUID | None = None,
) -> QueueMutationResponse:
    def apply_claim(queue: DataQueue, result: QueueMutationResponse) -> None:
        responseBytes = len(result.model_dump_json().encode("utf-8"))
        query = select_items(
            queue,
            status=payload.status,
            order=payload.order,
            itemId=payload.item_id,
        ).only("id", "data_json")[: payload.count]
        # NOTE: Django's iterator() returns a generator; django-stubs declares Iterator.
        with closing(
            cast(Generator[QueueItem], query.iterator(chunk_size=1))
        ) as candidates:
            for item in candidates:
                entry = QueueClaimedItemResponse(
                    id=item.id,
                    data=json.loads(item.data_json),
                )
                # Account for the entry, its ID, and both array separators; a replay cannot be larger.
                entryBytes = (
                    len(entry.model_dump_json().encode("utf-8"))
                    + len(str(item.id))
                    + 2
                    + 2 * bool(result.item_ids)
                )
                if responseBytes + entryBytes > MAX_QUEUE_RESPONSE_BYTES:
                    if not result.item_ids:
                        raise QueueOperationError(
                            "queue_response_too_large",
                            "This item cannot fit in one response.",
                        )
                    break
                result.items.append(entry)
                result.item_ids.append(item.id)
                responseBytes += entryBytes
        if result.item_ids:
            QueueItem.objects.filter(queue=queue, pk__in=result.item_ids).update(
                status=QueueItem.Status.CLAIMED,
                last_claimed_by_id=access.actorId,
                last_claimed_by_name=str(access.actor),
                last_claimed_at=result.accepted_at,
            )

    return _mutate_items(
        access,
        queueReference,
        payload,
        operation="claim",
        applyChange=apply_claim,
        apiKeyId=apiKeyId,
    )


@sensitive_variables()
def reset_items(
    access: OrganizationAccessContext,
    queueReference: uuid.UUID | str,
    payload: QueueResetRequest,
    *,
    apiKeyId: uuid.UUID | None = None,
) -> QueueMutationResponse:
    def apply_reset(queue: DataQueue, result: QueueMutationResponse) -> None:
        itemIds = list(dict.fromkeys(payload.item_ids))
        statusById = dict(
            QueueItem.objects.filter(queue=queue, pk__in=itemIds).values_list(
                "id", "status"
            ),
        )
        result.missing_ids.extend(
            itemId for itemId in itemIds if itemId not in statusById
        )
        result.skipped_ids.extend(
            itemId
            for itemId in itemIds
            if statusById.get(itemId) == QueueItem.Status.UNCLAIMED
        )
        result.item_ids.extend(
            itemId
            for itemId in itemIds
            if statusById.get(itemId) == QueueItem.Status.CLAIMED
        )
        QueueItem.objects.filter(
            queue=queue,
            pk__in=result.item_ids,
        ).update(status=QueueItem.Status.UNCLAIMED)

    return _mutate_items(
        access,
        queueReference,
        payload,
        operation="reset",
        applyChange=apply_reset,
        apiKeyId=apiKeyId,
    )


@sensitive_variables()
def delete_items(
    access: OrganizationAccessContext,
    queueReference: uuid.UUID | str,
    payload: QueueDeleteItemsRequest,
    *,
    apiKeyId: uuid.UUID | None = None,
) -> QueueMutationResponse:
    def apply_delete(queue: DataQueue, result: QueueMutationResponse) -> None:
        if payload.item_ids is not None:
            itemIds = list(dict.fromkeys(payload.item_ids))
            existingIds = set(
                QueueItem.objects.filter(queue=queue, pk__in=itemIds).values_list(
                    "id", flat=True
                ),
            )
            result.item_ids.extend(itemId for itemId in itemIds if itemId in existingIds)
            result.missing_ids.extend(
                itemId for itemId in itemIds if itemId not in existingIds
            )
        else:
            result.item_ids.extend(
                select_items(
                    queue,
                    status=payload.status,
                    order=payload.order,
                ).values_list("id", flat=True)[: payload.count],
            )
        QueueItem.objects.filter(queue=queue, pk__in=result.item_ids).delete()

    return _mutate_items(
        access,
        queueReference,
        payload,
        operation="delete_items",
        applyChange=apply_delete,
        apiKeyId=apiKeyId,
    )
