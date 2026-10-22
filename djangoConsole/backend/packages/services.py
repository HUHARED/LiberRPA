# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
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

from operations.contracts import AuditAction
from operations.audit import record_audit
from organizations.limits import get_organization_limits
from organizations.permissions import OrganizationAccessContext
from organizations.validators import get_path_name_key

from .archive import PackageArchiveMetadata, read_package_archive
from .cleanup import expire_uploads
from .contracts import (
    PackageReferenceKind,
    PackagePreparationState,
    PackageUploadRequest,
    PackageSettingsRequest,
    PackageUploadState,
)
from .models import (
    Package,
    PackageUpload,
    PackageUploadChunk,
    PackagePreparation,
)
from .queries import (
    require_package_department,
    get_package_query,
    build_package_payload,
    get_upload_state,
    build_upload_payload,
)
from .runtime import apply_run_settings, validate_run_settings


@dataclass(frozen=True)
class PackageUploadValidationResult:
    """Record which uploaded file passed validation; write permission must still be checked at commit."""

    uploadId: uuid.UUID
    blobId: uuid.UUID
    sizeBytes: int
    sha256: str
    fileSignature: tuple[int, int, int, int]
    metadata: PackageArchiveMetadata


def create_upload(
    access: OrganizationAccessContext, payload: PackageUploadRequest
) -> PackageUpload:
    require_package_department(access, payload.department_id, manage=True)
    existing = PackageUpload.objects.filter(
        organization=access.organization,
        actor_id=access.actorId,
        request_id=payload.request_id,
    ).first()
    if existing is not None:
        if (existing.department_id, existing.size_bytes, existing.sha256) != (
            payload.department_id,
            payload.size_bytes,
            payload.sha256,
        ):
            raise FileOperationError(
                "request_conflict", "This request ID has different upload parameters."
            )
        return existing
    if payload.size_bytes > settings.CONSOLE_LIMITS.maxPackageBytes:
        raise FileOperationError(
            "package_too_large", "The Package exceeds the archive size limit.", 413
        )
    expire_uploads(access.organization.pk)
    if (
        PackageUpload.objects.filter(organization=access.organization).count()
        >= settings.CONSOLE_LIMITS.maxFileReceiptsPerOrganization
    ):
        raise FileOperationError(
            "upload_receipt_limit", "The upload request history is full."
        )
    require_upload_slot(access.organization)
    lock_storage()
    usage = get_storage_usage(access.organization)
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
        purpose=StoredBlobPurpose.PACKAGE,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
    )
    return PackageUpload.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=payload.department_id,
        request_id=payload.request_id,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        blob=blob,
        expires_at=timezone.now() + timedelta(hours=24),
    )


def append_chunk(
    upload: PackageUpload, offset: int, chunkData: bytes, chunkSha256: str
) -> None:
    strState = get_upload_state(upload)
    if (
        offset < upload.offset
        and strState in (PackageUploadState.RECEIVING, PackageUploadState.COMPLETED)
        and PackageUploadChunk.objects.filter(
            upload=upload, offset=offset, size_bytes=len(chunkData), sha256=chunkSha256
        ).exists()
    ):
        return
    if strState != PackageUploadState.RECEIVING:
        raise FileOperationError(
            "upload_unavailable", "This upload is no longer receiving data.", 410
        )
    if offset != upload.offset or offset + len(chunkData) > upload.size_bytes:
        raise FileOperationError(
            "chunk_offset_conflict", "Use the confirmed offset and declared Package size."
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
                "upload_data_missing", "Confirmed upload bytes are unavailable.", 503
            )
        handle.truncate(offset)
        handle.flush()
        os.fsync(handle.fileno())
        check_disk_capacity()
        handle.seek(offset)
        handle.write(chunkData)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(path.parent)
    upload.offset += len(chunkData)
    upload.save(update_fields=["offset"])
    StoredBlob.objects.filter(pk=upload.blob_id).update(written_bytes=upload.offset)
    PackageUploadChunk.objects.create(
        upload=upload, offset=offset, size_bytes=len(chunkData), sha256=chunkSha256
    )


def _require_uploaded_blob(upload: PackageUpload) -> uuid.UUID:
    if get_upload_state(upload) != PackageUploadState.RECEIVING:
        raise FileOperationError(
            "upload_unavailable", "This upload is no longer available.", 410
        )
    if upload.offset != upload.size_bytes:
        raise FileOperationError(
            "upload_incomplete", "Upload all bytes before completing this Package."
        )
    if upload.blob_id is None:
        raise FileOperationError(
            "upload_data_missing", "The upload storage is unavailable.", 503
        )
    return upload.blob_id


def _get_file_signature(fileStat: os.stat_result) -> tuple[int, int, int, int]:
    return (
        fileStat.st_dev,
        fileStat.st_ino,
        fileStat.st_size,
        fileStat.st_mtime_ns,
    )


def validate_upload_content(
    upload: PackageUpload,
) -> PackageUploadValidationResult | FileOperationError:
    """Read complete content outside the organization transaction; persist nothing here."""
    blobId = _require_uploaded_blob(upload)
    try:
        with get_blob_path(blobId).open("rb") as handle:
            fileStat = os.fstat(handle.fileno())
            if (
                fileStat.st_size != upload.size_bytes
                or hashlib.file_digest(handle, "sha256").hexdigest() != upload.sha256
            ):
                raise FileOperationError(
                    "package_checksum_mismatch",
                    "The Package checksum does not match its declared content.",
                )
            handle.seek(0)
            metadata = read_package_archive(handle)
            fileSignature = _get_file_signature(fileStat)
            if _get_file_signature(os.fstat(handle.fileno())) != fileSignature:
                raise FileOperationError(
                    "upload_content_changed",
                    "The uploaded content changed during validation. Upload the Package again.",
                )
        return PackageUploadValidationResult(
            uploadId=upload.pk,
            blobId=blobId,
            sizeBytes=upload.size_bytes,
            sha256=upload.sha256,
            fileSignature=fileSignature,
            metadata=metadata,
        )
    except ValidationError as e:
        return FileOperationError("invalid_package", " ".join(e.messages), 400)
    except FileOperationError as e:
        return e


def complete_upload(
    access: OrganizationAccessContext,
    upload: PackageUpload,
    validationResult: PackageUploadValidationResult | FileOperationError,
) -> dict | FileOperationError:
    """Save the package after rechecking upload access while the organization is locked."""

    def validate_package_capacity(projectNameKey: str) -> None:
        limits = get_organization_limits(access.organization)
        intPackageCount = Package.objects.filter(
            department_id=upload.department_id, project_name_key=projectNameKey
        ).count()
        if intPackageCount >= limits.maxPackagesPerProject:
            raise FileOperationError(
                "package_limit", "This project has reached its package limit."
            )
        if (
            intPackageCount == 0
            and Package.objects
            .filter(department__organization=access.organization)
            .values("department_id", "project_name_key")
            .distinct()
            .count()
            >= limits.maxProjectsPerOrganization
        ):
            raise FileOperationError(
                "package_project_limit",
                "The organization has reached its Package project limit.",
            )

    if get_upload_state(upload) == PackageUploadState.COMPLETED:
        return build_upload_payload(upload)
    blobId = _require_uploaded_blob(upload)
    if isinstance(validationResult, PackageUploadValidationResult) and (
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
        purpose=StoredBlobPurpose.PACKAGE,
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
        # Fully received uploads cannot grow; duplicate chunks return without rewriting the file.
        if (
            _get_file_signature(get_blob_path(blobId).stat())
            != validationResult.fileSignature
        ):
            raise FileOperationError(
                "upload_content_changed",
                "The uploaded content changed during validation. Upload the Package again.",
            )
        metadata = validationResult.metadata
        strNameKey = get_path_name_key(metadata.projectName)
        strVersionKey = get_path_name_key(metadata.projectVersion)
        if Package.objects.filter(
            department_id=upload.department_id,
            project_name_key=strNameKey,
            project_version_key=strVersionKey,
        ).exists():
            raise FileOperationError(
                "package_exists",
                "This department already contains the project version; versions cannot be overwritten.",
            )
        validate_package_capacity(strNameKey)
    except FileOperationError as e:
        # Return validation failures so the caller commits the failure and cleanup marker.
        upload.state = PackageUploadState.FAILED
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=blobId).update(state=StoredBlobState.GARBAGE)
        return e

    package = Package(
        department_id=upload.department_id,
        project_name=metadata.projectName,
        project_name_key=strNameKey,
        project_version=metadata.projectVersion,
        project_version_key=strVersionKey,
        description=metadata.description,
        version_summary=metadata.versionSummary,
        requires_liberrpa=metadata.requiresLiberrpa,
        component_dependencies=metadata.componentDependencies,
        argument_names=[entry[0] for entry in metadata.runSettings.custom_prj_args],
        blob_id=upload.blob_id,
        uploaded_by_id=access.actorId,
        uploaded_by_name=str(access.actor),
    )
    apply_run_settings(package, metadata.runSettings)
    package.save(force_insert=True)
    StoredBlob.objects.filter(pk=upload.blob_id).update(
        state=StoredBlobState.AVAILABLE, written_bytes=upload.size_bytes
    )
    upload.state = PackageUploadState.COMPLETED
    upload.result = build_package_payload(
        package, access, runSettings=metadata.runSettings
    )
    upload.save(update_fields=["state", "result"])
    record_audit(
        AuditAction.PACKAGES_UPLOAD,
        actor=access.actor,
        organization=access.organization,
        target=package,
        channel=access.channel,
        metadata={
            "project_name": package.project_name,
            "project_version": package.project_version,
            "size_bytes": upload.size_bytes,
        },
    )
    return build_upload_payload(upload)


def cancel_upload(upload: PackageUpload) -> None:
    if get_upload_state(upload) == PackageUploadState.RECEIVING:
        upload.state = PackageUploadState.CANCELED
        upload.save(update_fields=["state"])
        StoredBlob.objects.filter(pk=upload.blob_id).update(state=StoredBlobState.GARBAGE)


def save_package_settings(
    access: OrganizationAccessContext,
    package: Package,
    payload: PackageSettingsRequest,
) -> None:
    require_package_department(access, package.department_id, manage=True)
    runSettings = validate_run_settings(package, payload.settings)
    if not set(payload.api_input_keys) <= set(package.argument_names):
        raise ValidationError({
            "api_input_keys": "API input keys must name existing custom arguments."
        })
    apply_run_settings(package, runSettings)
    package.api_input_keys = payload.api_input_keys
    boolEnvironmentChanged = (
        package.python_environment_name != payload.python_environment_name
    )
    package.python_environment_name = payload.python_environment_name
    package.updated_at = timezone.now()
    package.save(
        update_fields=[
            *type(runSettings).model_fields,
            "api_input_keys",
            "python_environment_name",
            "updated_at",
        ]
    )
    from .preparation import request_referenced_preparation

    if boolEnvironmentChanged:
        # Remove pending preparation requests that use the old environment setting.
        PackagePreparation.objects.filter(
            package=package,
            state__in=[
                PackagePreparationState.PENDING,
                PackagePreparationState.PREPARING,
            ],
        ).exclude(python_environment_name=package.python_environment_name).delete()
    request_referenced_preparation(package)
    record_audit(
        AuditAction.PACKAGES_UPDATE,
        actor=access.actor,
        organization=access.organization,
        target=package,
        channel=access.channel,
    )


def prepare_download(
    access: OrganizationAccessContext,
    package: Package,
    proxySnapshot: DownloadProxySnapshot | None,
) -> dict:
    require_download_slot(access.organization, proxySnapshot)
    path = get_blob_path(package.blob_id)
    if not path.is_file() or path.stat().st_size != package.blob.size_bytes:
        raise FileOperationError(
            "package_content_unavailable", "The Package content is unavailable.", 503
        )
    strSuffix = ".rpa.zip"
    strName = f"{package.project_name}_{package.project_version}"
    transfer = DownloadSession.objects.create(
        organization=access.organization,
        actor_id=access.actorId,
        department_id=package.department_id,
        blob=package.blob,
        # Preserve the suffix within DownloadSession.name's 128-character limit.
        name=strName[: 128 - len(strSuffix)] + strSuffix,
        expires_at=get_download_expiry(),
    )
    return {
        "transfer_id": str(transfer.pk),
        "file_name": transfer.name,
        "expires_at": transfer.expires_at.isoformat(),
        "package": build_package_payload(package, access),
    }


def open_download(
    access: OrganizationAccessContext, transferId: uuid.UUID
) -> tuple[DownloadSession, BinaryIO]:
    transfer = DownloadSession.objects.select_related("blob").get(
        pk=transferId,
        organization=access.organization,
        actor_id=access.actorId,
        blob__purpose=StoredBlobPurpose.PACKAGE,
    )
    require_package_department(access, transfer.department_id)
    if transfer.started or transfer.expires_at <= timezone.now():
        raise FileOperationError("transfer_expired", "Start a new Package download.", 410)
    if not get_package_query(access).filter(blob=transfer.blob).exists():
        raise FileOperationError(
            "package_not_found", "The Package is no longer available.", 404
        )
    handle = get_blob_path(transfer.blob_id).open("rb")
    try:
        if os.fstat(handle.fileno()).st_size != transfer.blob.size_bytes:
            raise FileOperationError(
                "package_content_unavailable", "The Package content is unavailable.", 503
            )
        transfer.started = True
        transfer.expires_at = get_download_expiry()
        transfer.save(update_fields=["started", "expires_at"])
        record_audit(
            AuditAction.PACKAGES_DOWNLOAD,
            actor=access.actor,
            organization=access.organization,
            target=transfer,
            channel=access.channel,
        )
    except Exception:
        handle.close()
        raise
    return transfer, handle


def get_package_references(package: Package) -> list[dict[str, str]]:
    from schedules.models import Schedule
    from runs.contracts import JobState
    from runs.models import Job

    listReference: list[dict[str, str]] = [
        {
            "kind": PackageReferenceKind.SCHEDULE,
            "id": str(schedule.pk),
            "name": schedule.name,
        }
        for schedule in Schedule.objects.filter(package=package, deleted_at__isnull=True)
    ]
    listReference.extend(
        {"kind": PackageReferenceKind.JOB, "id": str(job.pk), "name": str(job.pk)}
        for job in Job.objects.filter(package_id=package.pk).exclude(
            state=JobState.FINISHED
        )
    )
    listReference.extend(
        {
            "kind": PackageReferenceKind.PREPARATION,
            "id": str(preparation.pk),
            "name": f"{preparation.executor.name} / {preparation.python_environment_name}",
        }
        for preparation in PackagePreparation.objects
        .filter(
            package=package,
            state__in=[
                PackagePreparationState.PENDING,
                PackagePreparationState.PREPARING,
            ],
        )
        .select_related("executor")
        .order_by("executor__name", "python_environment_name", "pk")
    )
    # An unused authorization and an open proxy stream still protect the Package.
    downloadFilter = Q(expires_at__gt=timezone.now())
    if settings.CONSOLE_FILE_TRANSFER_PROXY is not None:
        downloadFilter |= Q(started=True)
    listReference.extend(
        {
            "kind": PackageReferenceKind.DOWNLOAD,
            "id": str(transfer.pk),
            "name": transfer.name,
        }
        for transfer in DownloadSession.objects.filter(
            downloadFilter, blob_id=package.blob_id
        ).order_by("expires_at", "pk")
    )
    return listReference


def delete_package(access: OrganizationAccessContext, package: Package) -> None:
    require_package_department(access, package.department_id, manage=True)
    if get_package_references(package):
        raise FileOperationError(
            "package_in_use",
            "Remove Schedule references, finish or close active Jobs, cancel preparation requests, and finish downloads or wait for unused links to expire.",
        )
    record_audit(
        AuditAction.PACKAGES_DELETE,
        actor=access.actor,
        organization=access.organization,
        target=package,
        channel=access.channel,
    )
    from schedules.models import Schedule

    Schedule.objects.filter(package=package, deleted_at__isnull=False).delete()
    blobId = package.blob_id
    package.delete()
    StoredBlob.objects.filter(pk=blobId).update(state=StoredBlobState.GARBAGE)
