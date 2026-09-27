# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.db.models.functions import Lower

from organizations.department_queries import get_department_path
from organizations.models import Department, DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .models import Asset, SECRET_ASSET_TYPES


def get_asset_query(access: OrganizationAccessContext) -> QuerySet[Asset]:
    return Asset.objects.filter(
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        )
    ).defer("encrypted_value")


def build_asset_payloads(
    assets: list[Asset], access: OrganizationAccessContext, *, includeValue: bool = False
) -> list[dict[str, object]]:
    departmentsById = {
        department.id: department
        for department in Department.objects.filter(
            organization=access.organization, deleted_at__isnull=True
        )
    }
    managedDepartmentIds = set(
        get_authorized_departments(
            access, requiredRole=DepartmentRole.DEVELOPER
        ).values_list("id", flat=True)
    )
    listPayload: list[dict[str, object]] = []
    for asset in assets:
        strDepartmentPath = get_department_path(
            departmentsById[asset.department_id], departmentsById
        )
        boolSecret = asset.asset_type in SECRET_ASSET_TYPES
        boolCanManage = asset.department_id in managedDepartmentIds
        strSummary = "Configured" if boolSecret else asset.value_json
        dictPayload: dict[str, object] = {
            "id": asset.id,
            "name": asset.name,
            "department": {"id": asset.department_id, "path": strDepartmentPath},
            "path": f"/{strDepartmentPath}/{asset.name}",
            "asset_type": asset.asset_type,
            "notes": asset.notes,
            "value_summary": strSummary
            if len(strSummary) <= 160
            else strSummary[:160] + "…",
            "can_manage": boolCanManage,
            "can_edit_value": boolCanManage if boolSecret else True,
            "created_at": asset.created_at,
            "updated_at": asset.updated_at,
        }
        if includeValue and not boolSecret:
            dictPayload["value"] = json.loads(asset.value_json)
        listPayload.append(dictPayload)
    return listPayload


def get_asset_list(
    access: OrganizationAccessContext,
    *,
    pageNumber: int = 1,
    departmentIds: tuple[uuid.UUID, ...] = (),
    name: str = "",
    assetTypes: tuple[str, ...] = (),
) -> dict[str, object]:
    assets = get_asset_query(access)
    if departmentIds:
        assets = assets.filter(department_id__in=departmentIds)
    if name:
        assets = assets.filter(name__icontains=name)
    if assetTypes:
        assets = assets.filter(asset_type__in=assetTypes)
    paginator = Paginator(assets.order_by(Lower("name"), "id"), 50)
    page = paginator.page(pageNumber)
    return {
        "assets": build_asset_payloads(list(page.object_list), access),
        "page": page.number,
        "page_size": 50,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
    }
