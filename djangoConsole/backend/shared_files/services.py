# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from file_storage.models import (
    StoredBlobPurpose,
    StoredBlobState,
    StoredBlob,
    DownloadSession,
)
from file_storage.proxy import DownloadProxySnapshot
from file_storage.services import (
    FileOperationError,
    get_blob_path,
    sync_directory,
    open_blob_for_write,
    lock_storage,
    check_disk_capacity,
    get_storage_usage,
    require_upload_slot,
    require_download_slot,
    get_download_expiry,
)
from operations.audit import record_audit
from organizations.department_queries import (
    get_department_tree,
    resolve_department_path,
    get_department_path,
)
from organizations.contracts import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)
from organizations.validators import get_path_name_key

from .contracts import (
    UploadState,
    FileUploadRequest,
    FileDeleteRequest,
    FileUploadResponse,
    FileDeleteResponse,
    FileDownloadResponse,
)
from .models import (
    SharedFile,
    UploadSession,
    UploadChunk,
    FileDeletionReceipt,
)
from .queries import (
    require_file_department_access,
    build_file_payload,
    resolve_file,
    get_upload_state,
    build_upload_payload,
)
from .cleanup import expire_uploads

_UPLOAD_LIFETIME_HOURS = 24


@dataclass(frozen=True)
class FileUploadValidationResult:
    """Identify the verified content; current access and upload state are checked at commit."""

    uploadId: uuid.UUID
    blobId: uuid.UUID
    sizeBytes: int
    sha256: str
    fileSignature: tuple[int, int, int, int]


def _get_request_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _prune_receipts_and_require_capacity(access: OrganizationAccessContext) -> None:
    cutoff = timezone.now() - timedelta(
        days=settings.CONSOLE_LIMITS.fileReceiptRetentionDays
    )
    # Never evict an unexpired identity to make room for a new mutation.
    UploadSession.objects.filter(
        organization=access.organization, created_at__lt=cutoff
    ).exclude(state=UploadState.RECEIVING).delete()
    FileDeletionReceipt.objects.filter(
        organization=access.organization, created_at__lt=cutoff
    ).delete()
    intReceiptCount = (
        UploadSession.objects.filter(organization=access.organization).count()
        + FileDeletionReceipt.objects.filter(organization=access.organization).count()
    )
    if intReceiptCount >= settings.CONSOLE_LIMITS.maxFileReceiptsPerOrganization:
        raise FileOperationError(
            "file_receipt_limit",
            "The file request history is full. Please try again later.",
        )


def _require_file_capacity(
    organizationId: uuid.UUID, existingFile: SharedFile | None
) -> None:
    if (
        existingFile is None
        and SharedFile.objects.filter(department__organization_id=organizationId).count()
        >= settings.CONSOLE_LIMITS.maxSharedFilesPerOrganization
    ):
        raise FileOperationError(
            "shared_file_limit", "The organization has reached its shared file limit."
        )


def create_upload(
    access: OrganizationAccessContext,
    payload: FileUploadRequest,
    pathParts: tuple[str, ...],
) -> UploadSession:
    """Reserve storage after the caller locks current access and parses the path."""
    strRequestDigest = _get_request_digest({
        "path": [get_path_name_key(strPart) for strPart in pathParts],
        "size": payload.size_bytes,
        "sha256": payload.sha256,
        "overwrite": payload.overwrite,
    })
    existingUpload = UploadSession.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
    ).first()
    if existingUpload is not None:
        require_file_department_access(access, existingUpload.department_id)
        if existingUpload.request_digest != strRequestDigest:
            raise FileOperationError(
                "request_conflict",
                "This request ID was already used with different parameters.",
            )
        return existingUpload
    departmentsById = get_department_tree(access.organization.pk)
    department = resolve_department_path(pathParts[:-1], departmentsById)
    require_file_department_access(access, department.pk)
    if payload.size_bytes > settings.CONSOLE_LIMITS.maxSharedFileBytes:
        raise FileOperationError(
            "file_too_large", "The file exceeds the single-file size limit.", 413
        )
    existingFile = SharedFile.objects.filter(
        department=department, name_key=get_path_name_key(pathParts[-1])
    ).first()
    if existingFile is not None and not payload.overwrite:
        raise FileOperationError(
            "file_exists",
            "A file with this name already exists. Enable Overwrite Existing File to replace it.",
        )
    _require_file_capacity(access.organization.pk, existingFile)
    expire_uploads(access.organization.pk)
    _prune_receipts_and_require_capacity(access)
    require_upload_slot(access.organization.pk)
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
        purpose=StoredBlobPurpose.SHARED_FILE,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
    )
    return UploadSession.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=department.pk,
        request_id=payload.request_id,
        request_digest=strRequestDigest,
        name=pathParts[-1],
        overwrite=payload.overwrite,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        blob=blob,
        expires_at=timezone.now() + timedelta(hours=_UPLOAD_LIFETIME_HOURS),
    )


def append_chunk(
    upload: UploadSession, offset: int, chunkData: bytes, chunkSha256: str
) -> UploadSession:
    """Apply bytes already size-checked and hashed at the HTTP boundary under the organization lock."""
    state = get_upload_state(upload)
    if offset < upload.offset:
        if (
            state in (UploadState.RECEIVING, UploadState.COMPLETED)
            and UploadChunk.objects.filter(
                upload=upload,
                offset=offset,
                size_bytes=len(chunkData),
                sha256=chunkSha256,
            ).exists()
        ):
            return upload
        raise FileOperationError(
            "chunk_conflict",
            "The chunk conflicts with confirmed bytes. Check the upload status.",
        )
    if state != UploadState.RECEIVING:
        raise FileOperationError(
            "upload_unavailable", "This upload is no longer receiving data.", 410
        )
    if offset != upload.offset or offset + len(chunkData) > upload.size_bytes:
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
        handle.write(chunkData)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(path.parent)
    upload.offset += len(chunkData)
    upload.save(update_fields=["offset"])
    StoredBlob.objects.filter(pk=upload.blob_id).update(written_bytes=upload.offset)
    UploadChunk.objects.create(
        upload=upload, offset=offset, size_bytes=len(chunkData), sha256=chunkSha256
    )
    return upload


def cancel_upload(upload: UploadSession) -> UploadSession:
    if get_upload_state(upload) == UploadState.RECEIVING:
        upload.state = UploadState.CANCELED
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=upload.blob_id).update(state=StoredBlobState.GARBAGE)
    return upload


def _require_uploaded_blob(upload: UploadSession) -> uuid.UUID:
    if get_upload_state(upload) != UploadState.RECEIVING:
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
    return upload.blob_id


def prepare_upload_validation(upload: UploadSession) -> None:
    """Check completeness and create an empty file under the organization lock, without syncing it."""
    blobId = _require_uploaded_blob(upload)
    if upload.size_bytes == 0:
        path = get_blob_path(blobId)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("xb"):
                pass


def _get_file_signature(fileStat: os.stat_result) -> tuple[int, int, int, int]:
    return (
        fileStat.st_dev,
        fileStat.st_ino,
        fileStat.st_size,
        fileStat.st_mtime_ns,
    )


def validate_upload_content(
    upload: UploadSession,
) -> FileUploadValidationResult | FileOperationError:
    """Verify complete content outside the organization transaction without creating or truncating files."""
    blobId = _require_uploaded_blob(upload)
    path = get_blob_path(blobId)
    try:
        # Chunks are already durable; only a newly created empty file still needs syncing.
        with path.open("r+b") if upload.size_bytes == 0 else path.open("rb") as handle:
            fileStat = os.fstat(handle.fileno())
            if fileStat.st_size < upload.size_bytes:
                return FileOperationError(
                    "upload_data_missing",
                    "Previously confirmed upload data is unavailable.",
                    503,
                )
            if (
                fileStat.st_size != upload.size_bytes
                or hashlib.file_digest(handle, "sha256").hexdigest() != upload.sha256
            ):
                return FileOperationError(
                    "file_checksum_mismatch",
                    "The file checksum does not match. Select the source file and start a new upload.",
                )
            if upload.size_bytes == 0:
                os.fsync(handle.fileno())
            fileSignature = _get_file_signature(fileStat)
            if _get_file_signature(os.fstat(handle.fileno())) != fileSignature:
                return FileOperationError(
                    "upload_content_changed",
                    "The uploaded content changed during validation. Upload the file again.",
                )
        if upload.size_bytes == 0:
            sync_directory(path.parent.parent)
            sync_directory(path.parent)
    except FileNotFoundError:
        return FileOperationError(
            "upload_data_missing", "The upload storage is unavailable.", 503
        )
    return FileUploadValidationResult(
        uploadId=upload.pk,
        blobId=blobId,
        sizeBytes=upload.size_bytes,
        sha256=upload.sha256,
        fileSignature=fileSignature,
    )


def complete_upload(
    access: OrganizationAccessContext,
    upload: UploadSession,
    validationResult: FileUploadValidationResult | FileOperationError,
    *,
    apiKeyId: uuid.UUID | None = None,
) -> FileUploadResponse | FileOperationError:
    """Publish verified content after the caller locks and rechecks current access."""
    if get_upload_state(upload) == UploadState.COMPLETED:
        return build_upload_payload(upload)
    blobId = _require_uploaded_blob(upload)
    if isinstance(validationResult, FileUploadValidationResult) and (
        validationResult.uploadId != upload.pk
        or validationResult.blobId != blobId
        or validationResult.sizeBytes != upload.size_bytes
        or validationResult.sha256 != upload.sha256
    ):
        raise FileOperationError(
            "upload_changed", "The upload changed. Check its status and try again."
        )
    if not StoredBlob.objects.filter(
        pk=blobId,
        organization=access.organization,
        purpose=StoredBlobPurpose.SHARED_FILE,
        state=StoredBlobState.RECEIVING,
        size_bytes=upload.size_bytes,
        written_bytes=upload.size_bytes,
        sha256=upload.sha256,
    ).exists():
        raise FileOperationError(
            "upload_data_missing", "The upload storage is unavailable.", 503
        )
    try:
        if isinstance(validationResult, FileOperationError):
            raise validationResult
        # Fully received uploads cannot grow; duplicate chunks never rewrite confirmed content.
        if (
            _get_file_signature(get_blob_path(blobId).stat())
            != validationResult.fileSignature
        ):
            raise FileOperationError(
                "upload_content_changed",
                "The uploaded content changed during validation. Upload the file again.",
            )
        existingFile = SharedFile.objects.filter(
            department_id=upload.department_id, name_key=get_path_name_key(upload.name)
        ).first()
        if existingFile is not None and not upload.overwrite:
            raise FileOperationError(
                "file_exists",
                "A file with this name was created during this upload. Enable Overwrite Existing File to replace it.",
            )
        _require_file_capacity(access.organization.pk, existingFile)
    except FileOperationError as e:
        if e.status >= 500:
            raise
        upload.state = UploadState.FAILED
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=blobId).update(state=StoredBlobState.GARBAGE)
        # Return the expected failure so the view can commit its terminal state before replying.
        return e
    if existingFile is not None:
        oldBlobId = existingFile.blob_id
        existingFile.delete()
        StoredBlob.objects.filter(pk=oldBlobId).update(state=StoredBlobState.GARBAGE)
    file = SharedFile.objects.create(
        department_id=upload.department_id,
        name=upload.name,
        name_key=get_path_name_key(upload.name),
        blob_id=upload.blob_id,
        uploaded_by_id=access.actorId,
        uploaded_by_name=str(access.actor),
    )
    StoredBlob.objects.filter(pk=upload.blob_id).update(
        state=StoredBlobState.AVAILABLE, written_bytes=upload.size_bytes
    )
    departmentsById = get_department_tree(access.organization.pk)
    filePayload = build_file_payload(
        file,
        "/" + get_department_path(departmentsById[upload.department_id], departmentsById),
    )
    upload.state = UploadState.COMPLETED
    upload.result = filePayload.model_dump(mode="json")
    upload.save(update_fields=["state", "result"])
    dictMetadata: dict[str, object] = {
        "path": filePayload.path,
        "size_bytes": upload.size_bytes,
    }
    if apiKeyId is not None:
        dictMetadata["api_key_id"] = str(apiKeyId)
    record_audit(
        "shared_files.overwrite" if existingFile is not None else "shared_files.upload",
        actor=access.actor,
        organization=access.organization,
        target=file,
        channel=access.channel,
        metadata=dictMetadata,
    )
    return build_upload_payload(upload, filePayload=filePayload)


def delete_files(
    access: OrganizationAccessContext,
    payload: FileDeleteRequest,
    paths: list[tuple[str, ...]],
    *,
    apiKeyId: uuid.UUID | None = None,
) -> FileDeleteResponse:
    pathPartsByNormalizedPath = {
        tuple(get_path_name_key(strPart) for strPart in parts): parts for parts in paths
    }
    strRequestDigest = _get_request_digest(sorted(pathPartsByNormalizedPath))
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
            not {uuid.UUID(strValue) for strValue in receipt.department_ids}
            <= allowedDepartmentIds
        ):
            raise PermissionDenied("The department is unavailable.")
        if receipt.request_digest != strRequestDigest:
            raise FileOperationError(
                "request_conflict",
                "This request ID was already used with different parameters.",
            )
        return FileDeleteResponse.model_validate(receipt.result, strict=False)
    departmentsById = get_department_tree(access.organization.pk)
    targets = [
        (resolve_department_path(parts[:-1], departmentsById), parts[-1])
        for parts in pathPartsByNormalizedPath.values()
    ]
    # Authorize the whole batch before checking any file's existence or changing anything.
    if not {department.pk for department, _ in targets} <= allowedDepartmentIds:
        raise PermissionDenied("The department is unavailable.")
    _prune_receipts_and_require_capacity(access)
    deletedPaths: list[str] = []
    missingPaths: list[str] = []
    for department, strName in targets:
        strDepartmentPath = "/" + get_department_path(department, departmentsById)
        file = SharedFile.objects.filter(
            department=department, name_key=get_path_name_key(strName)
        ).first()
        if file is None:
            missingPaths.append(f"{strDepartmentPath}/{strName}")
            continue
        strPath = f"{strDepartmentPath}/{file.name}"
        dictMetadata: dict[str, object] = {"path": strPath}
        if apiKeyId is not None:
            dictMetadata["api_key_id"] = str(apiKeyId)
        record_audit(
            "shared_files.delete",
            actor=access.actor,
            organization=access.organization,
            target=file,
            channel=access.channel,
            metadata=dictMetadata,
        )
        blobId = file.blob_id
        file.delete()
        StoredBlob.objects.filter(pk=blobId).update(state=StoredBlobState.GARBAGE)
        deletedPaths.append(strPath)
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
        request_digest=strRequestDigest,
        department_ids=sorted({str(department.pk) for department, _ in targets}),
        result=result.model_dump(mode="json"),
    )
    return result


def prepare_download(
    access: OrganizationAccessContext,
    pathParts: tuple[str, ...],
    proxySnapshot: DownloadProxySnapshot | None,
) -> FileDownloadResponse:
    file, strDepartmentPath = resolve_file(access, pathParts)
    require_download_slot(access.organization.pk, proxySnapshot)
    physicalPath = get_blob_path(file.blob_id)
    if not physicalPath.is_file() or physicalPath.stat().st_size != file.blob.size_bytes:
        raise FileOperationError(
            "file_content_unavailable",
            "The file content is temporarily unavailable.",
            503,
        )
    filePayload = build_file_payload(file, strDepartmentPath)
    transfer = DownloadSession.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=file.department_id,
        blob=file.blob,
        resource_path=filePayload.path,
        name=file.name,
        expires_at=get_download_expiry(),
    )
    return FileDownloadResponse(
        transfer_id=transfer.pk, expires_at=transfer.expires_at, file=filePayload
    )


def open_download(
    access: OrganizationAccessContext,
    transferId: uuid.UUID,
    *,
    apiKeyId: uuid.UUID | None = None,
) -> tuple[DownloadSession, BinaryIO]:
    transfer = DownloadSession.objects.select_related("blob").get(
        pk=transferId, organization=access.organization, actor_id=access.actorId
    )
    require_file_department_access(access, transfer.department_id)
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
        dictMetadata: dict[str, object] = {"path": transfer.resource_path}
        if apiKeyId is not None:
            dictMetadata["api_key_id"] = str(apiKeyId)
        record_audit(
            "shared_files.download",
            actor=access.actor,
            organization=access.organization,
            target=transfer,
            channel=access.channel,
            metadata=dictMetadata,
        )
    except Exception:
        handle.close()
        raise
    return transfer, handle
