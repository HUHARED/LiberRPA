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
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from accounts.models import User
from file_storage.models import StoredBlob, DownloadSession
from file_storage.services import (
    FileOperationError,
    get_blob_path,
    sync_directory,
    open_blob_for_write,
    lock_storage,
    check_disk_capacity,
    get_storage_usage,
    require_transfer_slot,
    get_download_expiry,
)
from operations.audit import record_audit
from organizations.models import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)
from organizations.validators import path_name_key

from .contracts import (
    FileUploadRequest,
    FileDeleteRequest,
    FileUploadResponse,
    FileDeleteResponse,
    FileDownloadResponse,
)
from .models import SharedFile, UploadSession, UploadChunk, FileDeletionReceipt
from .paths import (
    load_department_tree,
    require_department,
    resolve_department,
    build_department_path,
)
from .queries import (
    build_file_payload,
    resolve_file,
    get_upload_state,
    build_upload_payload,
)
from .cleanup import expire_uploads

_UPLOAD_LIFETIME_HOURS = 24


def _digest_request(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _check_receipt_capacity(access: OrganizationAccessContext) -> None:
    cutoff = timezone.now() - timedelta(
        days=settings.CONSOLE_LIMITS.fileReceiptRetentionDays
    )
    # Never evict an unexpired identity to make room for a new mutation.
    UploadSession.objects.filter(
        organization=access.organization, created_at__lt=cutoff
    ).exclude(state="receiving").delete()
    FileDeletionReceipt.objects.filter(
        organization=access.organization, created_at__lt=cutoff
    ).delete()
    receiptCount = (
        UploadSession.objects.filter(organization=access.organization).count()
        + FileDeletionReceipt.objects.filter(organization=access.organization).count()
    )
    if receiptCount >= settings.CONSOLE_LIMITS.maxFileReceiptsPerOrganization:
        raise FileOperationError(
            "file_receipt_limit",
            "The file request history is full. Please try again later.",
        )


def create_upload(
    access: OrganizationAccessContext,
    payload: FileUploadRequest,
    pathParts: tuple[str, ...],
) -> UploadSession:
    """Reserve storage after the caller locks current access and parses the path."""
    requestDigest = _digest_request({
        "path": [path_name_key(part) for part in pathParts],
        "size": payload.size_bytes,
        "sha256": payload.sha256,
        "overwrite": payload.overwrite,
    })
    existing = UploadSession.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
    ).first()
    if existing is not None:
        require_department(access, existing.department_id)
        if existing.request_digest != requestDigest:
            raise FileOperationError(
                "request_conflict",
                "This request ID was already used with different parameters.",
            )
        return existing
    departmentsById = load_department_tree(access.organization.pk)
    department = resolve_department(pathParts[:-1], departmentsById)
    require_department(access, department.pk)
    if payload.size_bytes > settings.CONSOLE_LIMITS.maxSharedFileBytes:
        raise FileOperationError(
            "file_too_large", "The file exceeds the single-file size limit.", 413
        )
    if (
        not payload.overwrite
        and SharedFile.objects.filter(
            department=department, name_key=path_name_key(pathParts[-1])
        ).exists()
    ):
        raise FileOperationError(
            "file_exists",
            "A file with this name already exists. Enable Overwrite Existing File to replace it.",
        )
    expire_uploads(access.organization.pk)
    _check_receipt_capacity(access)
    require_transfer_slot(access.organization.pk)
    lock_storage()
    usage = get_storage_usage(access.organization.pk)
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
        purpose="shared_file",
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
    )
    return UploadSession.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=department.pk,
        request_id=payload.request_id,
        request_digest=requestDigest,
        name=pathParts[-1],
        overwrite=payload.overwrite,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        blob=blob,
        expires_at=timezone.now() + timedelta(hours=_UPLOAD_LIFETIME_HOURS),
    )


def append_chunk(
    upload: UploadSession, offset: int, data: bytes, chunkSha256: str
) -> UploadSession:
    """Apply bytes already size-checked and hashed at the HTTP boundary under the organization lock."""
    state = get_upload_state(upload)
    if offset < upload.offset:
        if (
            state in ("receiving", "completed")
            and UploadChunk.objects.filter(
                upload=upload, offset=offset, size_bytes=len(data), sha256=chunkSha256
            ).exists()
        ):
            return upload
        raise FileOperationError(
            "chunk_conflict",
            "The chunk conflicts with confirmed bytes. Check the upload status.",
        )
    if state != "receiving":
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
    path, handle = open_blob_for_write(upload.blob_id)
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
        # A failed database commit may leave an unconfirmed tail; discard it before checking disk space.
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
        upload=upload, offset=offset, size_bytes=len(data), sha256=chunkSha256
    )
    return upload


def cancel_upload(upload: UploadSession) -> UploadSession:
    if get_upload_state(upload) == "receiving":
        upload.state = "canceled"
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=upload.blob_id).update(
            state=StoredBlob.State.GARBAGE
        )
    return upload


def complete_upload(
    access: OrganizationAccessContext, upload: UploadSession
) -> FileUploadResponse | FileOperationError:
    state = get_upload_state(upload)
    if state == "completed":
        return build_upload_payload(upload)
    if state != "receiving":
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
    # Verification and publication share one transaction; there is no committed intermediate state.
    path, handle = open_blob_for_write(upload.blob_id)
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
        department_id=upload.department_id, name_key=path_name_key(upload.name)
    ).first()
    failure = None
    if actualSize != upload.size_bytes or digest != upload.sha256:
        failure = FileOperationError(
            "file_checksum_mismatch",
            "The file checksum does not match. Select the source file and start a new upload.",
        )
    elif existing is not None and not upload.overwrite:
        failure = FileOperationError(
            "file_exists",
            "A file with this name was created during this upload. Enable Overwrite Existing File to replace it.",
        )
    if failure is not None:
        upload.state = "failed"
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=upload.blob_id).update(
            state=StoredBlob.State.GARBAGE
        )
        # Return the expected failure so the view can commit its terminal state before replying.
        return failure
    if existing is not None:
        oldBlobId = existing.blob_id
        existing.delete()
        StoredBlob.objects.filter(pk=oldBlobId).update(state=StoredBlob.State.GARBAGE)
    file = SharedFile.objects.create(
        department_id=upload.department_id,
        name=upload.name,
        name_key=path_name_key(upload.name),
        blob_id=upload.blob_id,
        uploaded_by_id=access.actorId,
        uploaded_by_name=str(User.objects.get(pk=access.actorId)),
    )
    StoredBlob.objects.filter(pk=upload.blob_id).update(
        state=StoredBlob.State.AVAILABLE, written_bytes=upload.size_bytes
    )
    departmentsById = load_department_tree(access.organization.pk)
    filePayload = build_file_payload(
        file,
        build_department_path(departmentsById[upload.department_id], departmentsById),
    )
    upload.state = "completed"
    upload.result = filePayload.model_dump(mode="json")
    upload.save(update_fields=["state", "result"])
    record_audit(
        "shared_files.overwrite" if existing is not None else "shared_files.upload",
        actorId=access.actorId,
        organization=access.organization,
        target=file,
        channel=access.channel,
        metadata={"path": filePayload.path, "size_bytes": upload.size_bytes},
    )
    return build_upload_payload(upload, filePayload=filePayload)


def delete_files(
    access: OrganizationAccessContext,
    payload: FileDeleteRequest,
    paths: list[tuple[str, ...]],
) -> FileDeleteResponse:
    normalized = {tuple(path_name_key(part) for part in parts): parts for parts in paths}
    requestDigest = _digest_request(sorted(normalized))
    receipt = FileDeletionReceipt.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
    ).first()
    allowedDepartmentIds = set(
        get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ).values_list("pk", flat=True)
    )
    if receipt is not None:
        if (
            not {uuid.UUID(value) for value in receipt.department_ids}
            <= allowedDepartmentIds
        ):
            raise PermissionDenied("The department is unavailable.")
        if receipt.request_digest != requestDigest:
            raise FileOperationError(
                "request_conflict",
                "This request ID was already used with different parameters.",
            )
        return FileDeleteResponse.model_validate(receipt.result, strict=False)
    departmentsById = load_department_tree(access.organization.pk)
    targets = [
        (resolve_department(parts[:-1], departmentsById), parts[-1])
        for parts in normalized.values()
    ]
    # Authorize the whole batch before checking any file's existence or changing anything.
    if not {department.pk for department, _ in targets} <= allowedDepartmentIds:
        raise PermissionDenied("The department is unavailable.")
    _check_receipt_capacity(access)
    deletedPaths: list[str] = []
    missingPaths: list[str] = []
    for department, name in targets:
        departmentPath = build_department_path(department, departmentsById)
        file = SharedFile.objects.filter(
            department=department, name_key=path_name_key(name)
        ).first()
        if file is None:
            missingPaths.append(f"{departmentPath}/{name}")
            continue
        path = f"{departmentPath}/{file.name}"
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
        StoredBlob.objects.filter(pk=blobId).update(state=StoredBlob.State.GARBAGE)
        deletedPaths.append(path)
    result = FileDeleteResponse(
        request_id=payload.request_id,
        deleted_paths=deletedPaths,
        missing_paths=missingPaths,
        deleted_count=len(deletedPaths),
    )
    FileDeletionReceipt.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
        request_digest=requestDigest,
        department_ids=sorted({str(department.pk) for department, _ in targets}),
        result=result.model_dump(mode="json"),
    )
    return result


def prepare_download(
    access: OrganizationAccessContext, pathParts: tuple[str, ...]
) -> FileDownloadResponse:
    file, departmentPath = resolve_file(access, pathParts)
    expire_uploads(access.organization.pk)
    require_transfer_slot(access.organization.pk)
    physicalPath = get_blob_path(file.blob_id)
    if not physicalPath.is_file() or physicalPath.stat().st_size != file.blob.size_bytes:
        raise FileOperationError(
            "file_content_unavailable",
            "The file content is temporarily unavailable.",
            503,
        )
    filePayload = build_file_payload(file, departmentPath)
    transfer = DownloadSession.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=file.department_id,
        blob=file.blob,
        path=filePayload.path,
        name=file.name,
        expires_at=get_download_expiry(),
    )
    return FileDownloadResponse(
        transfer_id=transfer.pk, expires_at=transfer.expires_at, file=filePayload
    )


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
    handle = get_blob_path(transfer.blob_id).open("rb")
    try:
        if os.fstat(handle.fileno()).st_size != transfer.blob.size_bytes:
            raise FileOperationError(
                "file_content_unavailable",
                "The file content is temporarily unavailable.",
                503,
            )
        transfer.started = True
        transfer.expires_at = get_download_expiry()
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
