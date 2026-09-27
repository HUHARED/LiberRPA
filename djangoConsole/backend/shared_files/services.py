# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import os
import uuid
from datetime import timedelta
from io import BufferedRandom
from pathlib import Path
from typing import BinaryIO

from django.conf import settings
from django.core.paginator import Paginator
from django.utils import timezone

from accounts.models import User
from file_storage.models import DownloadSession, StoredBlob
from file_storage.services import (
    CHUNK_BYTES,
    UPLOAD_LIFETIME_HOURS,
    FileOperationError,
    blob_path,
    check_disk_capacity,
    lease_expiry,
    lock_storage,
    require_transfer_slot,
    storage_usage,
    sync_directory,
)
from operations.audit import record_audit
from organizations.permissions import OrganizationAccessContext

from .contracts import (
    FileDeleteRequest,
    FileInfoResponse,
    FileListRequest,
    FileUploadRequest,
)
from .models import FileDeletionReceipt, SharedFile, UploadChunk, UploadSession
from .paths import (
    department_path,
    name_key,
    path_parts,
    require_department,
    resolve_department,
)


def file_info(file: SharedFile) -> dict[str, object]:
    path = department_path(file.department)
    return FileInfoResponse(
        path=f"{path}/{file.name}",
        name=file.name,
        department_path=path,
        size_bytes=file.blob.size_bytes,
        sha256=file.blob.sha256,
        uploaded_by_name=file.uploaded_by_name,
        uploaded_at=file.uploaded_at,
    ).model_dump(mode="json")


def resolve_file(access: OrganizationAccessContext, path: str) -> SharedFile:
    parts = path_parts(path)
    department = resolve_department(access, parts[:-1])
    return SharedFile.objects.select_related("department", "blob").get(
        department=department, name_key=name_key(parts[-1])
    )


def list_files(
    access: OrganizationAccessContext, payload: FileListRequest
) -> dict[str, object]:
    department = resolve_department(
        access, path_parts(payload.department_path, department=True)
    )
    query = SharedFile.objects.filter(department=department).select_related(
        "department", "blob"
    )
    if payload.name:
        query = query.filter(name_key__contains=name_key(payload.name))
    orderField = {
        "name": "name_key",
        "size": "blob__size_bytes",
        "uploaded_at": "uploaded_at",
    }[payload.sort_by]
    page = Paginator(
        query.order_by(("-" if payload.order == "desc" else "") + orderField, "id"), 100
    ).page(payload.page)
    return {
        "files": [file_info(file) for file in page],
        "department_path": department_path(department),
        "usage": storage_usage(access.organization.pk),
        "page": page.number,
        "page_size": 100,
        "total_count": page.paginator.count,
        "total_pages": page.paginator.num_pages,
    }


def digest_request(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def check_receipt_capacity(access: OrganizationAccessContext) -> None:
    cutoff = timezone.now() - timedelta(
        days=settings.CONSOLE_LIMITS.fileReceiptRetentionDays
    )
    # Never evict an unexpired identity to make room for a new mutation.
    UploadSession.objects.filter(
        organization=access.organization, created_at__lt=cutoff
    ).exclude(state__in=["receiving", "finalizing"]).delete()
    FileDeletionReceipt.objects.filter(
        organization=access.organization, created_at__lt=cutoff
    ).delete()
    count = (
        UploadSession.objects.filter(organization=access.organization).count()
        + FileDeletionReceipt.objects.filter(organization=access.organization).count()
    )
    if count >= settings.CONSOLE_LIMITS.maxFileReceiptsPerOrganization:
        raise FileOperationError(
            "file_receipt_limit",
            "The file request history is full. Please try again later.",
        )


def upload_info(upload: UploadSession) -> dict[str, object]:
    return {
        "upload_id": upload.pk,
        "state": upload.state,
        "offset": upload.offset,
        "size_bytes": upload.size_bytes,
        "chunk_bytes": CHUNK_BYTES,
        "expires_at": upload.expires_at,
        "file": upload.result,
    }


def get_upload(access: OrganizationAccessContext, uploadId: uuid.UUID) -> UploadSession:
    upload = UploadSession.objects.get(
        pk=uploadId, organization=access.organization, actor_id=access.actorId
    )
    require_department(access, upload.department_id)
    if upload.state == "receiving" and upload.expires_at <= timezone.now():
        upload.state = "expired"
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=upload.blob_id).update(state="garbage")
    return upload


def create_upload(
    access: OrganizationAccessContext, payload: FileUploadRequest
) -> UploadSession:
    parts = path_parts(payload.path)
    requestDigest = digest_request({
        "path": [name_key(part) for part in parts],
        "size": payload.size_bytes,
        "sha256": payload.sha256,
        "overwrite": payload.overwrite,
    })
    existing = UploadSession.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
    ).first()
    if existing:
        require_department(access, existing.department_id)
        if existing.request_digest != requestDigest:
            raise FileOperationError(
                "request_conflict",
                "This request ID was already used with different parameters.",
            )
        return get_upload(access, existing.pk)
    department = resolve_department(access, parts[:-1])
    if payload.size_bytes > settings.CONSOLE_LIMITS.maxSharedFileBytes:
        raise FileOperationError(
            "file_too_large", "The file exceeds the single-file size limit.", 413
        )
    if (
        not payload.overwrite
        and SharedFile.objects.filter(
            department=department, name_key=name_key(parts[-1])
        ).exists()
    ):
        raise FileOperationError(
            "file_exists",
            "A file with this name already exists. Enable Overwrite Existing File to replace it.",
        )
    check_receipt_capacity(access)
    require_transfer_slot(access.organization.pk)
    lock_storage()
    usage = storage_usage(access.organization.pk)
    if (
        usage["used_bytes"] + usage["reserved_bytes"] + payload.size_bytes
        > usage["limit_bytes"]
    ):
        raise FileOperationError(
            "storage_quota_exceeded", "The organization storage limit has been reached."
        )
    check_disk_capacity(payload.size_bytes)
    blob = StoredBlob.objects.create(
        organization=access.organization,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
    )
    return UploadSession.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=department.pk,
        request_id=payload.request_id,
        request_digest=requestDigest,
        name=parts[-1],
        overwrite=payload.overwrite,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        blob=blob,
        expires_at=timezone.now() + timedelta(hours=UPLOAD_LIFETIME_HOURS),
    )


def _prepare_blob_file(blobId: uuid.UUID) -> tuple[Path, BufferedRandom]:
    path = blob_path(blobId)
    path.parent.mkdir(parents=True, exist_ok=True)
    sync_directory(path.parent.parent)
    # The row is committed before disk creation; a failed write remains owned and charged.
    return path, path.open("r+b" if path.exists() else "w+b")


def append_chunk(
    upload: UploadSession, offset: int, data: bytes, sha256: str
) -> UploadSession:
    if not data or len(data) > CHUNK_BYTES:
        raise FileOperationError(
            "invalid_chunk_size", "Send a non-empty chunk of at most 4 MiB.", 400
        )
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise FileOperationError(
            "chunk_checksum_mismatch",
            "The chunk checksum does not match its content.",
            400,
        )
    if offset < upload.offset:
        if UploadChunk.objects.filter(
            upload=upload, offset=offset, size_bytes=len(data), sha256=digest
        ).exists():
            if upload.state in ("receiving", "completed"):
                return upload
        raise FileOperationError(
            "chunk_conflict",
            "The chunk conflicts with confirmed bytes. Check the upload status.",
        )
    if upload.state != "receiving":
        raise FileOperationError(
            "upload_unavailable", "This upload is no longer receiving data.", 410
        )
    if offset != upload.offset or offset + len(data) > upload.size_bytes:
        raise FileOperationError(
            "chunk_offset_conflict", "Use the confirmed offset and declared file size."
        )
    if upload.blob_id is None:
        raise FileOperationError(
            "upload_data_missing", "The upload storage is unavailable.", 503
        )
    lock_storage()
    path, handle = _prepare_blob_file(upload.blob_id)
    with handle:
        if os.fstat(handle.fileno()).st_size < offset:
            raise FileOperationError(
                "upload_data_missing",
                "Previously confirmed upload data is unavailable.",
                503,
            )
        handle.truncate(offset)
        handle.flush()
        os.fsync(handle.fileno())
        # Recover an unconfirmed tail before accounting for free disk space.
        check_disk_capacity()
        handle.seek(offset)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(path.parent)
    upload.offset += len(data)
    upload.save(update_fields=["offset"])
    StoredBlob.objects.filter(pk=upload.blob_id).update(written_bytes=upload.offset)
    UploadChunk.objects.create(
        upload=upload, offset=offset, size_bytes=len(data), sha256=digest
    )
    return upload


def cancel_upload(upload: UploadSession) -> UploadSession:
    if upload.state in ("receiving", "finalizing"):
        upload.state = "canceled"
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=upload.blob_id).update(state="garbage")
    return upload


def complete_upload(
    access: OrganizationAccessContext, upload: UploadSession
) -> UploadSession | FileOperationError:
    if upload.state == "completed":
        return upload
    if upload.state != "receiving":
        raise FileOperationError(
            "upload_unavailable", "This upload is no longer available.", 410
        )
    if upload.offset != upload.size_bytes:
        raise FileOperationError(
            "upload_incomplete", "Upload all bytes before completing this file."
        )
    if upload.blob_id is None:
        raise FileOperationError(
            "upload_data_missing", "The upload storage is unavailable.", 503
        )
    upload.state = "finalizing"
    upload.save(update_fields=["state"])
    # Synchronous verification is bounded by the 20 MiB single-file limit.
    path, handle = _prepare_blob_file(upload.blob_id)
    with handle:
        if os.fstat(handle.fileno()).st_size < upload.offset:
            raise FileOperationError(
                "upload_data_missing",
                "Previously confirmed upload data is unavailable.",
                503,
            )
        handle.truncate(upload.offset)
        handle.flush()
        os.fsync(handle.fileno())
        handle.seek(0)
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
        actualSize = os.fstat(handle.fileno()).st_size
    sync_directory(path.parent)
    existing = SharedFile.objects.filter(
        department_id=upload.department_id, name_key=name_key(upload.name)
    ).first()
    error = None
    if actualSize != upload.size_bytes or digest != upload.sha256:
        error = FileOperationError(
            "file_checksum_mismatch",
            "The file checksum does not match. Select the source file and start a new upload.",
        )
    elif existing and not upload.overwrite:
        error = FileOperationError(
            "file_exists",
            "A file with this name was created during this upload. Enable Overwrite Existing File to replace it.",
        )
    if error:
        upload.state = "failed"
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=upload.blob_id).update(state="garbage")
        # The view returns this error inside the transaction so the failed state commits.
        return error
    if existing:
        oldBlobId = existing.blob_id
        existing.delete()
        StoredBlob.objects.filter(pk=oldBlobId).update(state="garbage")
    file = SharedFile.objects.create(
        department_id=upload.department_id,
        name=upload.name,
        name_key=name_key(upload.name),
        blob_id=upload.blob_id,
        uploaded_by_id=access.actorId,
        uploaded_by_name=str(User.objects.get(pk=access.actorId)),
    )
    StoredBlob.objects.filter(pk=upload.blob_id).update(
        state="available", written_bytes=upload.size_bytes
    )
    upload.state = "completed"
    upload.result = file_info(file)
    upload.save(update_fields=["state", "result"])
    record_audit(
        "shared_files.overwrite" if existing else "shared_files.upload",
        actorId=access.actorId,
        organization=access.organization,
        target=file,
        channel=access.channel,
        metadata={"path": upload.result["path"], "size_bytes": upload.size_bytes},
    )
    return upload


def delete_files(
    access: OrganizationAccessContext, payload: FileDeleteRequest
) -> dict[str, object]:
    parsed = [path_parts(path) for path in payload.paths]
    normalized = {tuple(name_key(part) for part in parts): parts for parts in parsed}
    requestDigest = digest_request(sorted(normalized))
    receipt = FileDeletionReceipt.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
    ).first()
    if receipt:
        for departmentId in receipt.department_ids:
            require_department(access, uuid.UUID(departmentId))
        if receipt.request_digest != requestDigest:
            raise FileOperationError(
                "request_conflict",
                "This request ID was already used with different parameters.",
            )
        return receipt.result
    # Resolve and authorize every department before checking any file's existence.
    targets = [
        (resolve_department(access, parts[:-1]), parts[-1])
        for parts in normalized.values()
    ]
    check_receipt_capacity(access)
    deletedPaths, missingPaths = [], []
    for department, name in targets:
        file = SharedFile.objects.filter(
            department=department, name_key=name_key(name)
        ).first()
        if file is None:
            missingPaths.append(f"{department_path(department)}/{name}")
            continue
        path = f"{department_path(department)}/{file.name}"
        record_audit(
            "shared_files.delete",
            actorId=access.actorId,
            organization=access.organization,
            target=file,
            channel=access.channel,
            metadata={"path": path},
        )
        blobId = file.blob_id
        file.delete()
        StoredBlob.objects.filter(pk=blobId).update(state="garbage")
        deletedPaths.append(path)
    result: dict[str, object] = {
        "request_id": str(payload.request_id),
        "deleted_paths": deletedPaths,
        "missing_paths": missingPaths,
        "deleted_count": len(deletedPaths),
    }
    FileDeletionReceipt.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
        request_digest=requestDigest,
        department_ids=sorted({str(department.pk) for department, _ in targets}),
        result=result,
    )
    return result


def prepare_download(access: OrganizationAccessContext, path: str) -> dict[str, object]:
    file = resolve_file(access, path)
    require_transfer_slot(access.organization.pk)
    physicalPath = blob_path(file.blob_id)
    if not physicalPath.is_file() or physicalPath.stat().st_size != file.blob.size_bytes:
        raise FileOperationError(
            "file_content_unavailable",
            "The file content is temporarily unavailable.",
            503,
        )
    info = file_info(file)
    transfer = DownloadSession.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=file.department_id,
        blob=file.blob,
        path=info["path"],
        name=file.name,
        expires_at=lease_expiry(),
    )
    return {"transfer_id": transfer.pk, "expires_at": transfer.expires_at, "file": info}


def open_download(
    access: OrganizationAccessContext, transferId: uuid.UUID
) -> tuple[DownloadSession, BinaryIO]:
    transfer = DownloadSession.objects.select_related("blob").get(
        pk=transferId, organization=access.organization, actor_id=access.actorId
    )
    require_department(access, transfer.department_id)
    # Only an already opened download may outlive logical deletion or overwrite.
    if transfer.started or transfer.expires_at <= timezone.now():
        raise FileOperationError(
            "transfer_expired",
            "This download has expired or already started. Download the file again.",
            410,
        )
    if not SharedFile.objects.filter(blob=transfer.blob).exists():
        raise FileOperationError(
            "file_not_found",
            "The file changed or was deleted. Refresh the list and download it again.",
            404,
        )
    handle = blob_path(transfer.blob_id).open("rb")
    try:
        if os.fstat(handle.fileno()).st_size != transfer.blob.size_bytes:
            raise FileOperationError(
                "file_content_unavailable",
                "The file content is temporarily unavailable.",
                503,
            )
        transfer.started = True
        transfer.expires_at = lease_expiry()
        transfer.save(update_fields=["started", "expires_at"])
        record_audit(
            "shared_files.download",
            actorId=access.actorId,
            organization=access.organization,
            target=transfer,
            channel=access.channel,
            metadata={"path": transfer.path},
        )
    except Exception:
        handle.close()
        raise
    return transfer, handle
