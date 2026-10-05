# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import models
from django.utils import timezone

from console_project.constants import INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH


class SharedFile(models.Model):
    department_id: uuid.UUID
    blob_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey("organizations.Department", on_delete=models.PROTECT)
    name = models.CharField(max_length=128)
    name_key = models.TextField(editable=False, db_collation="C")
    blob = models.OneToOneField("file_storage.StoredBlob", on_delete=models.PROTECT)
    uploaded_by_id = models.UUIDField()
    uploaded_by_name = models.CharField(max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name_key"], name="shared_file_name_unique"
            )
        ]


class UploadState(models.TextChoices):
    RECEIVING = "receiving", "Receiving"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"
    CANCELED = "canceled", "Canceled"


class UploadSession(models.Model):
    organization_id: uuid.UUID
    blob_id: uuid.UUID | None

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    actor_id = models.UUIDField()
    department_id = models.UUIDField()
    request_id = models.UUIDField()
    request_digest = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    overwrite = models.BooleanField(default=False)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    # Terminal receipts survive cleanup of the underlying blob.
    blob = models.OneToOneField(
        "file_storage.StoredBlob", null=True, on_delete=models.SET_NULL
    )
    state = models.CharField(
        max_length=max(len(value) for value in UploadState.values),
        choices=UploadState.choices,
        default=UploadState.RECEIVING,
    )
    offset = models.PositiveBigIntegerField(default=0)
    result = models.JSONField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor_id", "request_id"],
                name="file_upload_request_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=UploadState.values),
                name="file_upload_state_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "state", "expires_at"], name="upload_org_expiry"
            )
        ]


class UploadChunk(models.Model):
    upload_id: uuid.UUID

    upload = models.ForeignKey(UploadSession, on_delete=models.CASCADE)
    offset = models.PositiveBigIntegerField()
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["upload", "offset"], name="upload_chunk_offset_unique"
            )
        ]


class FileDeletionReceipt(models.Model):
    organization_id: uuid.UUID

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    actor_id = models.UUIDField()
    request_id = models.UUIDField()
    request_digest = models.CharField(max_length=64)
    department_ids = models.JSONField()
    result = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor_id", "request_id"],
                name="file_delete_request_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "created_at"], name="file_delete_retention"
            )
        ]
