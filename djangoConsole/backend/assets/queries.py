# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from typing import cast

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.db.models.functions import Substr

from console_project.constants import INT_LIST_PAGE_SIZE
from organizations.department_queries import get_department_tree, get_department_path
from organizations.contracts import DepartmentRole
from organizations.validators import get_path_name_key
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import (
    AssetType,
    SECRET_ASSET_TYPES,
    AssetEntryResponse,
    AssetListResponse,
    AssetReferenceKind,
    AssetReferenceResponse,
    AssetDetailsEntryResponse,
    AssetDetailsResponse,
)
from .models import Asset


def get_asset_query(
    access: OrganizationAccessContext,
    *,
    requiredRole: DepartmentRole = DepartmentRole.OPERATOR,
) -> QuerySet[Asset]:
    return Asset.objects.filter(
        department__in=get_authorized_departments(access, requiredRole=requiredRole)
    ).defer("encrypted_value")


def get_asset_list(
    access: OrganizationAccessContext,
    *,
    pageNumber: int = 1,
    departmentIds: tuple[uuid.UUID, ...] = (),
    name: str = "",
    assetTypes: tuple[AssetType, ...] = (),
) -> AssetListResponse:
    assets = get_asset_query(access)
    if departmentIds:
        assets = assets.filter(department_id__in=departmentIds)
    if name:
        assets = assets.filter(name_key__contains=get_path_name_key(name))
    if assetTypes:
        assets = assets.filter(asset_type__in=assetTypes)
    # Fetch only the preview; neither complete values nor ciphertext belong in a list query.
    rows = assets.order_by("name_key", "id").values(
        "id",
        "name",
        "department_id",
        "asset_type",
        "notes",
        "created_at",
        "updated_at",
        value_summary=Substr("value_json", 1, 161),
    )
    paginator = Paginator(rows, INT_LIST_PAGE_SIZE)
    page = paginator.page(pageNumber)
    departmentsById = get_department_tree(access.organization.pk)
    managedDepartmentIds = set(
        get_authorized_departments(
            access, requiredRole=DepartmentRole.DEVELOPER
        ).values_list("id", flat=True)
    )
    listEntry: list[AssetEntryResponse] = []
    for row in page.object_list:
        departmentId = cast(uuid.UUID, row.pop("department_id"))
        strDepartmentPath = get_department_path(
            departmentsById[departmentId], departmentsById
        )
        boolSecret = row["asset_type"] in SECRET_ASSET_TYPES
        boolCanManage = departmentId in managedDepartmentIds
        strSummary = "Configured" if boolSecret else cast(str, row["value_summary"])
        row.update(
            department={"id": departmentId, "path": strDepartmentPath},
            path=f"/{strDepartmentPath}/{row['name']}",
            value_summary=strSummary
            if len(strSummary) <= 160
            else strSummary[:160] + "…",
            can_manage=boolCanManage,
            can_edit_value=boolCanManage if boolSecret else True,
        )
        listEntry.append(AssetEntryResponse.model_validate(row))
    return AssetListResponse(
        assets=listEntry,
        page=page.number,
        page_size=INT_LIST_PAGE_SIZE,
        total_count=paginator.count,
        total_pages=paginator.num_pages,
    )


def get_asset_references(
    asset: Asset, access: OrganizationAccessContext
) -> list[AssetReferenceResponse]:
    """Report visible saved bindings only; arbitrary Flow code is not inspected."""
    from packages.models import Package
    from schedules.models import Schedule

    if asset.asset_type in SECRET_ASSET_TYPES:
        return []
    departments = get_authorized_departments(
        access, requiredRole=DepartmentRole.OPERATOR
    ).filter(pk=asset.department_id)
    listReference = []
    listSource = [
        (
            AssetReferenceKind.PACKAGE,
            Package.objects.filter(department__in=departments).values(
                "id", "project_name", "project_version", "custom_arg_assets"
            ),
        ),
        (
            AssetReferenceKind.SCHEDULE,
            Schedule.objects.filter(
                department__in=departments, deleted_at__isnull=True
            ).values("id", "name", "custom_arg_assets"),
        ),
    ]
    for kind, rows in listSource:
        for row in rows:
            if any(
                binding is not None
                and binding["asset_type"] == asset.asset_type
                and get_path_name_key(binding["name"]) == asset.name_key
                for binding in (row["custom_arg_assets"] or [])
            ):
                listReference.append(
                    AssetReferenceResponse(
                        kind=kind,
                        id=row["id"],
                        name=row["project_name"]
                        if kind == AssetReferenceKind.PACKAGE
                        else row["name"],
                        project_version=row.get("project_version"),
                    )
                )
    return listReference


def build_asset_details(
    asset: Asset, access: OrganizationAccessContext
) -> AssetDetailsResponse:
    departmentsById = get_department_tree(access.organization.pk)
    strDepartmentPath = get_department_path(
        departmentsById[asset.department_id], departmentsById
    )
    boolSecret = asset.asset_type in SECRET_ASSET_TYPES
    boolCanManage = (
        get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER)
        .filter(pk=asset.department_id)
        .exists()
    )
    strSummary = "Configured" if boolSecret else asset.value_json
    dictPayload: dict[str, object] = {
        "id": asset.id,
        "name": asset.name,
        "department": {"id": asset.department_id, "path": strDepartmentPath},
        "path": f"/{strDepartmentPath}/{asset.name}",
        "asset_type": asset.asset_type,
        "notes": asset.notes,
        "value_summary": strSummary if len(strSummary) <= 160 else strSummary[:160] + "…",
        "can_manage": boolCanManage,
        "can_edit_value": boolCanManage if boolSecret else True,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
        "references": get_asset_references(asset, access),
    }
    if not boolSecret:
        dictPayload["value"] = json.loads(asset.value_json)
    return AssetDetailsResponse(
        asset=AssetDetailsEntryResponse.model_validate(dictPayload)
    )
