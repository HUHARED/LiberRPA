# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from organizations.models import Organization

from .models import DownloadSession, StorageLock, StoredBlob

CHUNK_BYTES = 4 * 1024 * 1024
TRANSFER_LEASE_SECONDS = 120
UPLOAD_LIFETIME_HOURS = 24
logger = logging.getLogger(__name__)


class FileOperationError(Exception):
    def __init__(self, code: str, message: str, status: int = 409) -> None:
        self.code = code
        self.status = status
        super().__init__(message)


def storage_root() -> Path:
    root = Path(settings.CONSOLE_STORAGE_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def blob_path(blobId: uuid.UUID) -> Path:
    # Only a server-created UUID can determine a physical path.
    return storage_root() / blobId.hex[:2] / blobId.hex


def sync_directory(path: Path) -> None:
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def lock_storage() -> None:
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError(
            "Storage reservations require a transaction and organization lock."
        )
    StorageLock.objects.get_or_create(pk=1)
    StorageLock.objects.select_for_update().get(pk=1)


def check_disk_capacity(additionalBytes: int = 0) -> None:
    # Caller holds the volume lock. Confirmed bytes already reduce disk_usage.free.
    pending = (
        StoredBlob.objects.aggregate(value=Sum(F("size_bytes") - F("written_bytes")))[
            "value"
        ]
        or 0
    )
    if (
        shutil.disk_usage(storage_root()).free - pending - additionalBytes
        < settings.CONSOLE_LIMITS.minStorageFreeBytes
    ):
        raise FileOperationError(
            "storage_unavailable",
            "Storage space is temporarily unavailable. Please try again later.",
            503,
        )


def storage_usage(organizationId: uuid.UUID) -> dict[str, int]:
    totals = {
        row["state"]: row["total"]
        for row in StoredBlob.objects
        .filter(organization_id=organizationId)
        .values("state")
        .annotate(total=Sum("size_bytes"))
    }
    return {
        "used_bytes": totals.get("available", 0) + totals.get("garbage", 0),
        "reserved_bytes": totals.get("receiving", 0),
        "pending_cleanup_bytes": totals.get("garbage", 0),
        "limit_bytes": settings.CONSOLE_LIMITS.maxStoredBytesPerOrganization,
        "max_file_bytes": settings.CONSOLE_LIMITS.maxSharedFileBytes,
    }


def expire_transfers(organizationId: uuid.UUID) -> None:
    """Caller holds the organization lock; disk cleanup happens after this commit."""
    from shared_files.models import UploadSession

    now = timezone.now()
    DownloadSession.objects.filter(
        organization_id=organizationId, expires_at__lte=now
    ).delete()
    uploads = UploadSession.objects.filter(
        organization_id=organizationId, state="receiving", expires_at__lte=now
    )
    StoredBlob.objects.filter(pk__in=uploads.values("blob_id")).update(state="garbage")
    uploads.update(state="expired")


def require_transfer_slot(organizationId: uuid.UUID) -> None:
    from shared_files.models import UploadSession

    expire_transfers(organizationId)
    count = DownloadSession.objects.filter(organization_id=organizationId).count()
    count += UploadSession.objects.filter(
        organization_id=organizationId, state__in=["receiving", "finalizing"]
    ).count()
    if count >= settings.CONSOLE_LIMITS.maxActiveTransfersPerOrganization:
        raise FileOperationError(
            "too_many_transfers",
            "Too many active transfers. Please try again later.",
            429,
        )


def lease_expiry() -> datetime:
    return timezone.now() + timedelta(seconds=TRANSFER_LEASE_SECONDS)


@transaction.atomic
def release_download(transferId: uuid.UUID, organizationId: uuid.UUID) -> None:
    if Organization.objects.select_for_update().filter(pk=organizationId).exists():
        DownloadSession.objects.filter(
            pk=transferId, organization_id=organizationId
        ).delete()


@transaction.atomic
def renew_download(transferId: uuid.UUID, organizationId: uuid.UUID) -> None:
    # An already opened transfer may finish after a role/account change.
    if not Organization.objects.select_for_update().filter(pk=organizationId).exists():
        raise FileOperationError("transfer_expired", "This download has expired.", 410)
    count = DownloadSession.objects.filter(
        pk=transferId,
        organization_id=organizationId,
        started=True,
        expires_at__gt=timezone.now(),
    ).update(expires_at=lease_expiry())
    if not count:
        raise FileOperationError("transfer_expired", "This download has expired.", 410)


@transaction.atomic
def collect_blob(blobId: uuid.UUID, organizationId: uuid.UUID) -> bool:
    """Delete committed garbage only; a failed transaction keeps the quota charged."""
    from shared_files.models import SharedFile

    if not Organization.objects.select_for_update().filter(pk=organizationId).exists():
        return False
    lock_storage()
    expire_transfers(organizationId)
    blob = StoredBlob.objects.filter(
        pk=blobId, organization_id=organizationId, state="garbage"
    ).first()
    if blob is None or DownloadSession.objects.filter(blob=blob).exists():
        return False
    # A programming error must never delete an actively published file.
    if SharedFile.objects.filter(blob=blob).exists():
        raise RuntimeError("A published file cannot be garbage collected.")
    path = blob_path(blob.pk)
    path.unlink(missing_ok=True)
    if path.parent.exists():
        sync_directory(path.parent)
    blob.delete()
    return True


@transaction.atomic
def prepare_organization_cleanup(organizationId: uuid.UUID) -> None:
    from shared_files.models import SharedFile, UploadSession

    organization = Organization.objects.select_for_update().get(pk=organizationId)
    if organization.deletion_started_at is None:
        raise RuntimeError("Organization deletion has not started.")
    expire_transfers(organizationId)
    SharedFile.objects.filter(department__organization_id=organizationId).delete()
    UploadSession.objects.filter(
        organization_id=organizationId, state__in=["receiving", "finalizing"]
    ).update(state="canceled")
    StoredBlob.objects.filter(organization_id=organizationId).update(state="garbage")


def clean_organization_storage(organizationId: uuid.UUID) -> bool:
    prepare_organization_cleanup(organizationId)
    for blobId in (
        StoredBlob.objects
        .filter(organization_id=organizationId)
        .values_list("pk", flat=True)
        .iterator()
    ):
        collect_blob(blobId, organizationId)
    return not StoredBlob.objects.filter(organization_id=organizationId).exists()


def cleanup_storage(limit: int = 200) -> tuple[int, int]:
    from shared_files.models import UploadSession

    # Bound each pass, with oldest expiry/creation first to avoid starvation.
    organizationIds = set(
        UploadSession.objects
        .filter(state="receiving", expires_at__lte=timezone.now())
        .order_by("expires_at")
        .values_list("organization_id", flat=True)[:limit]
    )
    organizationIds.update(
        DownloadSession.objects
        .filter(expires_at__lte=timezone.now())
        .order_by("expires_at")
        .values_list("organization_id", flat=True)[:limit]
    )
    for organizationId in organizationIds:
        with transaction.atomic():
            if (
                Organization.objects
                .select_for_update()
                .filter(pk=organizationId)
                .exists()
            ):
                expire_transfers(organizationId)
    deleted = failed = 0
    candidates = list(
        StoredBlob.objects
        .filter(state="garbage")
        .order_by("created_at", "pk")
        .values_list("pk", "organization_id")[:limit]
    )
    for blobId, organizationId in candidates:
        try:
            deleted += int(collect_blob(blobId, organizationId))
        except OSError:
            failed += 1
            logger.exception("Stored file cleanup failed; quota remains charged.")
    return deleted, failed
