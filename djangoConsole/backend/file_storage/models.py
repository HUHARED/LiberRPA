# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import models
from django.utils import timezone

from console_project.constants import INT_WINDOWS_NAME_MAX_LENGTH


class StorageLock(models.Model):
    """One lock for all reservations on the configured storage volume."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)


class StoredBlobPurpose(models.TextChoices):
    PACKAGE = "package", "Package"
    SHARED_FILE = "shared_file", "Shared File"


class StoredBlobState(models.TextChoices):
    RECEIVING = "receiving", "Receiving"
    AVAILABLE = "available", "Available"
    GARBAGE = "garbage", "Pending cleanup"


class StoredBlob(models.Model):
    organization_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECT prevents quota and disk ownership from disappearing through a cascade.
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    purpose = models.CharField(
        max_length=max(len(value) for value in StoredBlobPurpose.values),
        choices=StoredBlobPurpose.choices,
        default=StoredBlobPurpose.SHARED_FILE,
    )
    size_bytes = models.PositiveBigIntegerField()
    written_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    state = models.CharField(
        max_length=max(len(value) for value in StoredBlobState.values),
        choices=StoredBlobState.choices,
        default=StoredBlobState.RECEIVING,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(purpose__in=StoredBlobPurpose.values),
                name="blob_purpose_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=StoredBlobState.values),
                name="blob_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(written_bytes__lte=models.F("size_bytes")),
                name="blob_written_within_size",
            ),
        ]
        indexes = [models.Index(fields=["organization", "state"], name="blob_org_state")]


class DownloadSession(models.Model):
    organization_id: uuid.UUID
    blob_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    actor_id = models.UUIDField()
    department_id = models.UUIDField()
    blob = models.ForeignKey(StoredBlob, on_delete=models.PROTECT)
    # Snapshot the authorized resource path and download name; renames cannot alter this transfer.
    resource_path = models.TextField(blank=True, default="")
    name = models.CharField(max_length=INT_WINDOWS_NAME_MAX_LENGTH)
    started = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "expires_at"], name="download_org_expiry"
            )
        ]
