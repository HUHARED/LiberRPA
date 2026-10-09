# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.utils import timezone

from organizations.department_queries import get_department_tree, get_department_path
from organizations.models import DepartmentRole, Department
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import UPLOAD_CHUNK_BYTES
from .models import Package, PackageUpload, PackageUploadState
from .runtime import build_run_settings

_INT_PACKAGES_PER_PAGE = 50


def require_package_department(
    access: OrganizationAccessContext, departmentId: uuid.UUID, *, manage: bool = False
) -> Department:
    return get_authorized_departments(
        access,
        requiredRole=DepartmentRole.DEVELOPER if manage else DepartmentRole.OPERATOR,
    ).get(pk=departmentId)


def get_package_query(
    access: OrganizationAccessContext, *, manage: bool = False
) -> QuerySet[Package]:
    departments = get_authorized_departments(
        access,
        requiredRole=DepartmentRole.DEVELOPER if manage else DepartmentRole.OPERATOR,
    )
    return Package.objects.filter(department__in=departments).select_related(
        "department__organization", "blob"
    )


def build_package_payload(
    package: Package,
    access: OrganizationAccessContext,
    *,
    departmentTree: dict[uuid.UUID, Department] | None = None,
    manageableDepartmentIds: set[uuid.UUID] | None = None,
) -> dict:
    dictDepartment = (
        departmentTree
        if departmentTree is not None
        else get_department_tree(access.organization.pk)
    )
    if manageableDepartmentIds is None:
        manageableDepartmentIds = set(
            get_authorized_departments(
                access, requiredRole=DepartmentRole.DEVELOPER
            ).values_list("pk", flat=True)
        )
    return {
        "id": str(package.pk),
        "department_id": str(package.department_id),
        "department_path": "/" + get_department_path(package.department, dictDepartment),
        "project_name": package.project_name,
        "version": package.version,
        "description": package.description,
        "version_summary": package.version_summary,
        "requires_liberrpa": package.requires_liberrpa,
        "component_dependencies": package.component_dependencies,
        "sha256": package.sha256,
        "size_bytes": package.blob.size_bytes,
        "python_environment_name": package.python_environment_name,
        "settings": build_run_settings(package),
        "api_input_keys": package.api_input_keys,
        "uploaded_at": package.uploaded_at.isoformat(),
        "uploaded_by_name": package.uploaded_by_name,
        "can_manage": package.department_id in manageableDepartmentIds,
    }


def get_packages(
    access: OrganizationAccessContext, *, pageNumber: int, departmentIds: tuple, name: str
) -> dict:
    query = get_package_query(access)
    if departmentIds:
        query = query.filter(department_id__in=departmentIds)
    if name:
        query = query.filter(project_name__icontains=name)
    page = Paginator(
        query.order_by("project_name_key", "-uploaded_at", "pk"), _INT_PACKAGES_PER_PAGE
    ).page(pageNumber)
    dictDepartment = get_department_tree(access.organization.pk)
    setManageableDepartmentId = set(
        get_authorized_departments(
            access, requiredRole=DepartmentRole.DEVELOPER
        ).values_list("pk", flat=True)
    )
    return {
        "packages": [
            build_package_payload(
                package,
                access,
                departmentTree=dictDepartment,
                manageableDepartmentIds=setManageableDepartmentId,
            )
            for package in page.object_list
        ],
        "page": page.number,
        "page_size": _INT_PACKAGES_PER_PAGE,
        "total_count": page.paginator.count,
        "total_pages": page.paginator.num_pages,
    }


def get_upload(access: OrganizationAccessContext, uploadId: uuid.UUID) -> PackageUpload:
    upload = PackageUpload.objects.get(
        pk=uploadId, organization=access.organization, actor_id=access.actorId
    )
    require_package_department(access, upload.department_id, manage=True)
    return upload


def get_upload_state(upload: PackageUpload) -> str:
    if (
        upload.state == PackageUploadState.RECEIVING
        and upload.expires_at <= timezone.now()
    ):
        return PackageUploadState.EXPIRED
    return upload.state


def build_upload_payload(upload: PackageUpload) -> dict:
    return {
        "upload_id": str(upload.pk),
        "state": get_upload_state(upload),
        "offset": upload.offset,
        "size_bytes": upload.size_bytes,
        "chunk_bytes": UPLOAD_CHUNK_BYTES,
        "expires_at": upload.expires_at.isoformat(),
        "package": upload.result,
    }
