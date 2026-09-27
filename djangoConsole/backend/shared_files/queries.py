# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.conf import settings
from django.core.paginator import Paginator
from django.utils import timezone

from file_storage.services import get_storage_usage
from organizations.permissions import OrganizationAccessContext
from organizations.validators import path_name_key

from .contracts import (
    UPLOAD_CHUNK_BYTES,
    FileListRequest,
    FileInfoResponse,
    FileUsageResponse,
    FileListResponse,
    FileUploadResponse,
)
from .models import SharedFile, UploadSession
from .paths import (
    load_department_tree,
    require_department,
    resolve_department,
    build_department_path,
)


def build_file_payload(file: SharedFile, departmentPath: str) -> FileInfoResponse:
    return FileInfoResponse(
        path=f"{departmentPath}/{file.name}",
        name=file.name,
        department_path=departmentPath,
        size_bytes=file.blob.size_bytes,
        sha256=file.blob.sha256,
        uploaded_by_name=file.uploaded_by_name,
        uploaded_at=file.uploaded_at,
    )


def resolve_file(
    access: OrganizationAccessContext, pathParts: tuple[str, ...]
) -> tuple[SharedFile, str]:
    departmentsById = load_department_tree(access.organization.pk)
    department = resolve_department(pathParts[:-1], departmentsById)
    require_department(access, department.pk)
    file = SharedFile.objects.select_related("blob").get(
        department=department, name_key=path_name_key(pathParts[-1])
    )
    return file, build_department_path(department, departmentsById)


def get_file_list(
    access: OrganizationAccessContext,
    payload: FileListRequest,
    departmentParts: tuple[str, ...],
) -> FileListResponse:
    departmentsById = load_department_tree(access.organization.pk)
    department = resolve_department(departmentParts, departmentsById)
    require_department(access, department.pk)
    departmentPath = build_department_path(department, departmentsById)
    query = SharedFile.objects.filter(department=department).select_related("blob")
    if payload.name:
        query = query.filter(name_key__contains=path_name_key(payload.name))
    orderField = {
        "name": "name_key",
        "size": "blob__size_bytes",
        "uploaded_at": "uploaded_at",
    }[payload.sort_by]
    page = Paginator(
        query.order_by(("-" if payload.order == "desc" else "") + orderField, "id"), 100
    ).page(payload.page)
    return FileListResponse(
        files=[build_file_payload(file, departmentPath) for file in page],
        department_path=departmentPath,
        usage=FileUsageResponse(
            **get_storage_usage(access.organization.pk),
            max_file_bytes=settings.CONSOLE_LIMITS.maxSharedFileBytes,
        ),
        page=page.number,
        page_size=100,
        total_count=page.paginator.count,
        total_pages=page.paginator.num_pages,
    )


def get_upload_state(upload: UploadSession) -> str:
    # A status read reports expiry without acquiring a write lock or running cleanup.
    if upload.state == "receiving" and upload.expires_at <= timezone.now():
        return "expired"
    return upload.state


def build_upload_payload(
    upload: UploadSession, *, filePayload: FileInfoResponse | None = None
) -> FileUploadResponse:
    # A receipt is JSON loaded from persistence, not a response serialized earlier in this call.
    if filePayload is None and upload.result is not None:
        filePayload = FileInfoResponse.model_validate(upload.result, strict=False)
    return FileUploadResponse.model_validate({
        "upload_id": upload.pk,
        "state": get_upload_state(upload),
        "offset": upload.offset,
        "size_bytes": upload.size_bytes,
        "chunk_bytes": UPLOAD_CHUNK_BYTES,
        "expires_at": upload.expires_at,
        "file": filePayload,
    })


def get_upload(access: OrganizationAccessContext, uploadId: uuid.UUID) -> UploadSession:
    upload = UploadSession.objects.get(
        pk=uploadId, organization=access.organization, actor_id=access.actorId
    )
    require_department(access, upload.department_id)
    return upload
