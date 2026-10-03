# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.validators import MaxLengthValidator, ProhibitNullCharactersValidator
from django.db import models
from django.utils import timezone

from console_project.constants import INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH
from organizations.validators import validate_path_segment

from .contracts import QueueStatus


class DataQueue(models.Model):
    department_id: uuid.UUID
    unclaimed_count: int
    claimed_count: int
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, related_name="data_queues"
    )
    name = models.CharField(max_length=128, validators=[validate_path_segment])
    # NOTE: Name writes must update this key through the business service.
    name_key = models.TextField(editable=False, db_collation="C")
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
    next_sequence = models.PositiveBigIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name_key"],
                name="queue_department_name_unique",
                violation_error_code="duplicate_queue_name",
                violation_error_message="A queue with this name already exists in this department.",
            )
        ]

    def __str__(self) -> str:
        return self.name


class QueueItem(models.Model):
    summary: str

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    queue = models.ForeignKey(DataQueue, on_delete=models.CASCADE, related_name="items")
    sequence = models.PositiveBigIntegerField(editable=False)
    data_json = models.TextField(editable=False)
    size_bytes = models.PositiveIntegerField(editable=False)
    status = models.CharField(
        max_length=9,
        choices=[(state, state.value.title()) for state in QueueStatus],
        default=QueueStatus.UNCLAIMED,
    )
    # Historical identities survive account deletion without retaining an account foreign key.
    uploaded_by_id = models.UUIDField(editable=False)
    uploaded_by_name = models.CharField(
        max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH, editable=False
    )
    uploaded_at = models.DateTimeField(default=timezone.now, editable=False)
    last_claimed_by_id = models.UUIDField(null=True, editable=False)
    last_claimed_by_name = models.CharField(
        max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH,
        blank=True,
        default="",
        editable=False,
    )
    last_claimed_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["queue", "sequence"], name="queue_item_sequence_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(QueueStatus)),
                name="queue_item_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status=QueueStatus.UNCLAIMED)
                | models.Q(
                    last_claimed_by_id__isnull=False, last_claimed_at__isnull=False
                ),
                name="queue_claim_metadata_present",
            ),
        ]
        indexes = [
            models.Index(
                fields=["queue", "status", "sequence"], name="queue_item_selection"
            )
        ]


class QueueOperation(models.TextChoices):
    UPLOAD = "upload", "Upload"
    CLAIM = "claim", "Claim"
    RESET = "reset", "Reset"
    DELETE_ITEMS = "delete_items", "Delete Items"


class QueueReceipt(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    actor_id = models.UUIDField()
    operation = models.CharField(max_length=16, choices=QueueOperation.choices)
    request_id = models.UUIDField()
    request_digest = models.CharField(max_length=64)
    # Preserve original identities when a queue or department is removed and recreated.
    queue_id = models.UUIDField()
    department_id = models.UUIDField()
    result = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor_id", "operation", "request_id"],
                name="queue_receipt_request_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(operation__in=QueueOperation.values),
                name="queue_receipt_operation_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "created_at"], name="queue_receipt_retention"
            )
        ]
