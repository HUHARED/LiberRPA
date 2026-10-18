# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.paginator import Paginator
from django.db.models import F, Q, QuerySet, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from console_project.constants import INT_UPLOAD_CHUNK_BYTES

from organizations.department_queries import get_department_tree, get_department_path
from organizations.models import DepartmentRole, Department
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import PackageUploadState, RunSettings
from .models import Package, PackageUpload
from .runtime import parse_run_settings

_INT_PACKAGE_BROWSE_PAGE_SIZE = 50


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
    runSettings: RunSettings | None = None,
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
        if runSettings is None:
            runSettings = parse_run_settings(package)
        dictPayload.update({
            "description": package.description,
            "version_summary": package.version_summary,
            "requires_liberrpa": package.requires_liberrpa,
            "component_dependencies": package.component_dependencies,
            "sha256": package.sha256,
            "settings": runSettings.model_dump(mode="json"),
            "api_input_keys": package.api_input_keys,
        })
    return dictPayload


def _get_package_option_payloads(
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
        {
            **build_package_payload(
                package,
                access,
                details=False,
                departmentTree=dictDepartment,
                manageableDepartmentIds=setManageableDepartmentId,
            ),
            "project_name_key": package.project_name_key,
        }
        for package in query
    ]


def _build_package_project_group_payload(
    package: Package, departmentTree: dict[uuid.UUID, Department]
) -> dict:
    return {
        "department_id": str(package.department_id),
        "department_path": "/"
        + get_department_path(departmentTree[package.department_id], departmentTree),
        "project_name": package.project_name,
        "project_name_key": package.project_name_key,
    }


def get_package_project_groups(
    access: OrganizationAccessContext,
    *,
    pageNumber: int,
    departmentIds: tuple[uuid.UUID, ...],
    locatePackageId: uuid.UUID | None = None,
) -> dict:
    query = get_package_query(access).select_related(None)
    if departmentIds:
        query = query.filter(department_id__in=departmentIds)

    # Group by department and project name, using the most recently uploaded Package for each entry.
    latestPackagePerProject = query.annotate(
        package_rank=Window(
            expression=RowNumber(),
            partition_by=[F("department_id"), F("project_name_key")],
            order_by=[F("uploaded_at").desc(), F("pk").asc()],
        )
    ).filter(package_rank=1)
    if locatePackageId is not None:
        package = query.only("department_id", "project_name_key").get(pk=locatePackageId)
        intBefore = latestPackagePerProject.filter(
            Q(project_name_key__lt=package.project_name_key)
            | Q(
                project_name_key=package.project_name_key,
                department_id__lt=package.department_id,
            )
        ).count()
        pageNumber = intBefore // _INT_PACKAGE_BROWSE_PAGE_SIZE + 1

    page = Paginator(
        latestPackagePerProject.only(
            "id", "department_id", "project_name", "project_name_key"
        ).order_by("project_name_key", "department_id"),
        _INT_PACKAGE_BROWSE_PAGE_SIZE,
    ).page(pageNumber)
    dictDepartment = get_department_tree(access.organization.pk)
    return {
        "project_groups": [
            {
                **_build_package_project_group_payload(package, dictDepartment),
                "latest_package_id": str(package.pk),
            }
            for package in page
        ],
        "page": page.number,
        "page_size": _INT_PACKAGE_BROWSE_PAGE_SIZE,
        "total_count": page.paginator.count,
        "total_pages": page.paginator.num_pages,
    }


def get_project_packages(
    access: OrganizationAccessContext,
    packageId: uuid.UUID,
    *,
    pageNumber: int | None,
) -> dict:
    selectedPackage = (
        get_package_query(access)
        .select_related(None)
        .only("id", "department_id", "project_name", "project_name_key", "uploaded_at")
        .get(pk=packageId)
    )
    query = get_package_query(access).filter(
        department_id=selectedPackage.department_id,
        project_name_key=selectedPackage.project_name_key,
    )
    if pageNumber is None:
        intBefore = query.filter(
            Q(uploaded_at__gt=selectedPackage.uploaded_at)
            | Q(uploaded_at=selectedPackage.uploaded_at, pk__lt=selectedPackage.pk)
        ).count()
        pageNumber = intBefore // _INT_PACKAGE_BROWSE_PAGE_SIZE + 1

    page = Paginator(
        query
        .select_related(None)
        .only("id", "project_version")
        .order_by("-uploaded_at", "pk"),
        _INT_PACKAGE_BROWSE_PAGE_SIZE,
    ).page(pageNumber)
    return {
        "project_group": _build_package_project_group_payload(
            selectedPackage, get_department_tree(access.organization.pk)
        ),
        "packages": [
            {"id": str(package.pk), "project_version": package.project_version}
            for package in page
        ],
        "page": page.number,
        "page_size": _INT_PACKAGE_BROWSE_PAGE_SIZE,
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
    return {"packages": _get_package_option_payloads(access, query)}


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
