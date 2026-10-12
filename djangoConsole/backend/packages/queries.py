# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import cast

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.utils import timezone

from console_project.constants import INT_UPLOAD_CHUNK_BYTES

from organizations.department_queries import get_department_tree, get_department_path
from organizations.models import DepartmentRole, Department
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import PackageUploadState
from .models import Package, PackageUpload
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
    details: bool = True,
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
    dictPayload: dict[str, object] = {
        "id": str(package.pk),
        "department_id": str(package.department_id),
        "department_path": "/"
        + get_department_path(dictDepartment[package.department_id], dictDepartment),
        "project_name": package.project_name,
        "project_version": package.project_version,
        "size_bytes": package.blob.size_bytes,
        "python_environment_name": package.python_environment_name,
        "uploaded_at": package.uploaded_at.isoformat(),
        "uploaded_by_name": package.uploaded_by_name,
        "can_manage": package.department_id in manageableDepartmentIds,
    }
    if details:
        dictPayload.update({
            "description": package.description,
            "version_summary": package.version_summary,
            "requires_liberrpa": package.requires_liberrpa,
            "component_dependencies": package.component_dependencies,
            "sha256": package.sha256,
            "settings": build_run_settings(package).model_dump(mode="json"),
            "api_input_keys": package.api_input_keys,
        })
    return dictPayload


def _get_package_list_payloads(
    access: OrganizationAccessContext, query: QuerySet[Package]
) -> list[dict]:
    query = (
        query
        .select_related(None)
        .select_related("blob")
        .only(
            "id",
            "department_id",
            "project_name",
            "project_name_key",
            "project_version",
            "python_environment_name",
            "uploaded_at",
            "uploaded_by_name",
            "blob__size_bytes",
        )
    )
    dictDepartment = get_department_tree(access.organization.pk)
    setManageableDepartmentId = set(
        get_authorized_departments(
            access, requiredRole=DepartmentRole.DEVELOPER
        ).values_list("pk", flat=True)
    )
    return [
        build_package_payload(
            package,
            access,
            details=False,
            departmentTree=dictDepartment,
            manageableDepartmentIds=setManageableDepartmentId,
        )
        for package in query
    ]


def get_packages(
    access: OrganizationAccessContext,
    *,
    pageNumber: int,
    departmentIds: tuple[uuid.UUID, ...],
    projectName: str,
) -> dict:
    query = get_package_query(access)
    if departmentIds:
        query = query.filter(department_id__in=departmentIds)
    if projectName:
        query = query.filter(project_name__icontains=projectName)
    page = Paginator(
        query.order_by("project_name_key", "-uploaded_at", "pk"), _INT_PACKAGES_PER_PAGE
    ).page(pageNumber)
    return {
        "packages": _get_package_list_payloads(
            access, cast(QuerySet[Package], page.object_list)
        ),
        "page": page.number,
        "page_size": _INT_PACKAGES_PER_PAGE,
        "total_count": page.paginator.count,
        "total_pages": page.paginator.num_pages,
    }


def get_package_options(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> dict:
    department = require_package_department(access, departmentId)
    query = Package.objects.filter(department=department).order_by(
        "project_name_key", "-uploaded_at", "pk"
    )
    return {"packages": _get_package_list_payloads(access, query)}


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
        "chunk_bytes": INT_UPLOAD_CHUNK_BYTES,
        "expires_at": upload.expires_at.isoformat(),
        "package": upload.result,
    }
