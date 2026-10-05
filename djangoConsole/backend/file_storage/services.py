# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import errno
import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta
from io import BufferedRandom
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from organizations.models import Organization

from .models import StorageLock, StoredBlobState, StoredBlob, DownloadSession

_TRANSFER_LEASE_SECONDS = 120
_LOGGER = logging.getLogger("console.file_storage")


class FileOperationError(Exception):
    def __init__(self, code: str, message: str, status: int = 409) -> None:
        self.code = code
        self.status = status
        super().__init__(message)


def get_blob_path(blobId: uuid.UUID) -> Path:
    # Only a server-created UUID can determine a physical path; lookup creates nothing.
    return Path(settings.CONSOLE_STORAGE_ROOT) / blobId.hex[:2] / blobId.hex


def sync_directory(path: Path) -> None:
    if os.name != "nt":
        intDescriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(intDescriptor)
        finally:
            os.close(intDescriptor)


def open_blob_for_write(blobId: uuid.UUID) -> tuple[Path, BufferedRandom]:
    path = get_blob_path(blobId)
    path.parent.mkdir(parents=True, exist_ok=True)
    sync_directory(path.parent.parent)
    # The reservation commits before disk creation, so failed writes remain owned and charged.
    return path, path.open("r+b" if path.exists() else "w+b")


def lock_storage() -> None:
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError(
            "Storage reservations require a transaction and organization lock."
        )
    StorageLock.objects.get_or_create(pk=1)
    StorageLock.objects.select_for_update().get(pk=1)


def check_disk_capacity(additionalBytes: int = 0) -> None:
    # Caller holds the volume lock. Only receiving blobs can grow; written bytes already reduce disk_usage.free.
    intPendingBytes = (
        StoredBlob.objects.filter(state=StoredBlobState.RECEIVING).aggregate(
            value=Sum(F("size_bytes") - F("written_bytes"))
        )["value"]
        or 0
    )
    pathRoot = Path(settings.CONSOLE_STORAGE_ROOT)
    pathRoot.mkdir(parents=True, exist_ok=True)
    if (
        shutil.disk_usage(pathRoot).free - intPendingBytes - additionalBytes
        < settings.CONSOLE_LIMITS.minStorageFreeBytes
    ):
        raise FileOperationError(
            "storage_unavailable",
            "Storage space is temporarily unavailable. Please try again later.",
            503,
        )


def get_storage_usage(organizationId: uuid.UUID) -> dict[str, int]:
    totals = {
        row["state"]: row["total"]
        for row in StoredBlob.objects
        .filter(organization_id=organizationId)
        .values("state")
        .annotate(total=Sum("size_bytes"))
    }
    return {
        "used_bytes": totals.get(StoredBlobState.AVAILABLE, 0)
        + totals.get(StoredBlobState.GARBAGE, 0),
        "reserved_bytes": totals.get(StoredBlobState.RECEIVING, 0),
        "pending_cleanup_bytes": totals.get(StoredBlobState.GARBAGE, 0),
        "limit_bytes": settings.CONSOLE_LIMITS.maxStoredBytesPerOrganization,
    }


def _expire_downloads(organizationId: uuid.UUID) -> None:
    """Reclaim expired download leases while the caller holds the organization lock."""
    DownloadSession.objects.filter(
        organization_id=organizationId, expires_at__lte=timezone.now()
    ).delete()


def require_transfer_slot(organizationId: uuid.UUID) -> None:
    """Count storage reservations, not business upload models, under the organization lock."""
    _expire_downloads(organizationId)
    intTransferCount = DownloadSession.objects.filter(
        organization_id=organizationId
    ).count()
    intTransferCount += StoredBlob.objects.filter(
        organization_id=organizationId, state=StoredBlobState.RECEIVING
    ).count()
    from runs.models import RunFileTransfer

    RunFileTransfer.objects.filter(expires_at__lte=timezone.now()).delete()
    intTransferCount += RunFileTransfer.objects.filter(
        organization_id=organizationId
    ).count()
    if intTransferCount >= settings.CONSOLE_LIMITS.maxActiveTransfersPerOrganization:
        raise FileOperationError(
            "too_many_transfers",
            "Too many active transfers. Please try again later.",
            429,
        )


def get_download_expiry() -> datetime:
    return timezone.now() + timedelta(seconds=_TRANSFER_LEASE_SECONDS)


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
    intUpdatedCount = DownloadSession.objects.filter(
        pk=transferId,
        organization_id=organizationId,
        started=True,
        expires_at__gt=timezone.now(),
    ).update(expires_at=get_download_expiry())
    if not intUpdatedCount:
        raise FileOperationError("transfer_expired", "This download has expired.", 410)


@transaction.atomic
def _collect_blob(blobId: uuid.UUID, organizationId: uuid.UUID) -> bool:
    """Remove committed garbage without releasing capacity until physical deletion succeeds."""
    if not Organization.objects.select_for_update().filter(pk=organizationId).exists():
        return False
    lock_storage()
    _expire_downloads(organizationId)
    blob = StoredBlob.objects.filter(
        pk=blobId, organization_id=organizationId, state=StoredBlobState.GARBAGE
    ).first()
    if blob is None or DownloadSession.objects.filter(blob=blob).exists():
        return False
    path = get_blob_path(blob.pk)
    # Let Django check all PROTECT references before touching disk, without knowing their models.
    blob.delete()
    # An unlink/fsync failure rolls back the row deletion and keeps its capacity charged.
    path.unlink(missing_ok=True)
    if path.parent.exists():
        sync_directory(path.parent)
    # Empty shard cleanup must not prevent releasing the deleted file's capacity.
    try:
        path.parent.rmdir()
        sync_directory(path.parent.parent)
    except OSError as e:
        if e.errno not in (errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST):
            _LOGGER.warning(
                "Empty storage directory cleanup failed: %s", path.parent, exc_info=True
            )
    return True


def clean_organization_storage(organizationId: uuid.UUID) -> bool:
    """Business owners must first retire their references and mark their blobs as garbage."""
    for blobId in (
        StoredBlob.objects
        .filter(organization_id=organizationId, state=StoredBlobState.GARBAGE)
        .values_list("pk", flat=True)
        .iterator()
    ):
        _collect_blob(blobId, organizationId)
    return not StoredBlob.objects.filter(organization_id=organizationId).exists()


def cleanup_storage(limit: int = 200) -> tuple[int, int]:
    # Bound each pass, with oldest expiry/creation first.
    organizationIds = set(
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
                _expire_downloads(organizationId)
    intDeletedCount = intFailedCount = 0
    candidates = list(
        StoredBlob.objects
        .filter(state=StoredBlobState.GARBAGE)
        .order_by("created_at", "pk")
        .values_list("pk", "organization_id")[:limit]
    )
    for blobId, organizationId in candidates:
        try:
            intDeletedCount += int(_collect_blob(blobId, organizationId))
        except (OSError, ProtectedError):
            intFailedCount += 1
            _LOGGER.exception("Stored file cleanup failed; quota remains charged.")
    return intDeletedCount, intFailedCount
