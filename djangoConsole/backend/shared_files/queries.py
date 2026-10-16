# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.utils import timezone

from console_project.constants import INT_UPLOAD_CHUNK_BYTES
from file_storage.services import get_storage_usage
from organizations.department_queries import (
    get_department_tree,
    resolve_department_path,
    get_department_path,
)
from organizations.models import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)
from organizations.validators import get_path_name_key

from .contracts import (
    FileListRequest,
    FileInfoResponse,
    FileUsageResponse,
    FileListResponse,
    FileUploadResponse,
)
from .models import SharedFile, UploadState, UploadSession

_INT_FILES_PER_PAGE = 50


def require_file_department_access(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> None:
    """Check current file permissions without loading a department object a second time."""
    if (
        not get_authorized_departments(access, requiredRole=DepartmentRole.OPERATOR)
        .filter(pk=departmentId)
        .exists()
    ):
        raise PermissionDenied("The department is unavailable.")


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
    departmentsById = get_department_tree(access.organization.pk)
    department = resolve_department_path(pathParts[:-1], departmentsById)
    require_file_department_access(access, department.pk)
    file = SharedFile.objects.select_related("blob").get(
        department=department, name_key=get_path_name_key(pathParts[-1])
    )
    return file, "/" + get_department_path(department, departmentsById)


def get_file_list(
    access: OrganizationAccessContext,
    payload: FileListRequest,
    departmentParts: tuple[str, ...] | None,
) -> FileListResponse:
    departmentsById = get_department_tree(access.organization.pk)
    strDepartmentPath = None
    if departmentParts is None:
        query = SharedFile.objects.filter(
            department__in=get_authorized_departments(
                access, requiredRole=DepartmentRole.OPERATOR
            )
        )
    else:
        department = resolve_department_path(departmentParts, departmentsById)
        require_file_department_access(access, department.pk)
        strDepartmentPath = "/" + get_department_path(department, departmentsById)
        query = SharedFile.objects.filter(department=department)
    query = query.select_related("blob")
    if payload.name:
        query = query.filter(name_key__contains=get_path_name_key(payload.name))
    strOrderField = {
        "name": "name_key",
        "size": "blob__size_bytes",
        "uploaded_at": "uploaded_at",
    }[payload.sort_by]
    page = Paginator(
        query.order_by(("-" if payload.order == "desc" else "") + strOrderField, "id"),
        _INT_FILES_PER_PAGE,
    ).page(payload.page)
    return FileListResponse(
        files=[
            build_file_payload(
                file,
                strDepartmentPath
                if strDepartmentPath is not None
                else "/"
                + get_department_path(
                    departmentsById[file.department_id], departmentsById
                ),
            )
            for file in page
        ],
        department_path=strDepartmentPath,
        usage=FileUsageResponse(
            **get_storage_usage(access.organization.pk),
            max_file_bytes=settings.CONSOLE_LIMITS.maxSharedFileBytes,
        ),
        page=page.number,
        page_size=_INT_FILES_PER_PAGE,
        total_count=page.paginator.count,
        total_pages=page.paginator.num_pages,
    )


def get_upload_state(upload: UploadSession) -> UploadState:
    # A status read reports expiry without acquiring a write lock or running cleanup.
    if upload.state == UploadState.RECEIVING and upload.expires_at <= timezone.now():
        return UploadState.EXPIRED
    return UploadState(upload.state)


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
        "chunk_bytes": INT_UPLOAD_CHUNK_BYTES,
        "expires_at": upload.expires_at,
        "file": filePayload,
    })


def get_upload(access: OrganizationAccessContext, uploadId: uuid.UUID) -> UploadSession:
    upload = UploadSession.objects.get(
        pk=uploadId, organization=access.organization, actor_id=access.actorId
    )
    require_file_department_access(access, upload.department_id)
    return upload
