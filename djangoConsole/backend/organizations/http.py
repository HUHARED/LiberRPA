# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import TypedDict

from django.http import QueryDict

from console_project.http import parse_page_number

from .access import AccountAccessInfo
from .contracts import AccountAccessResponse


class DepartmentResourceListParameters(TypedDict):
    pageNumber: int
    departmentIds: tuple[uuid.UUID, ...]
    name: str


def parse_department_resource_filters(
    query: QueryDict, *, extraFields: frozenset[str] = frozenset()
) -> DepartmentResourceListParameters:
    """Parse shared list filters without granting access to the selected departments."""
    if set(query) - {"page", "department_id", "name"} - extraFields:
        raise ValueError("Unknown list filters.")
    if len(query.getlist("name")) > 1:
        raise ValueError("Send one name filter.")
    strName = query.get("name", "").strip()
    listDepartmentValue = query.getlist("department_id")
    if len(strName) > 128 or len(listDepartmentValue) > 100:
        raise ValueError("Too many filter values or an overlong name.")
    return {
        "pageNumber": parse_page_number(query),
        "departmentIds": tuple(
            uuid.UUID(strDepartmentValue) for strDepartmentValue in listDepartmentValue
        ),
        "name": strName,
    }


def build_account_access_payload(
    accountAccessInfo: AccountAccessInfo,
) -> dict[str, object]:
    """Map internal access attributes to the shared HTTP response fields."""
    organizationInfo = accountAccessInfo.organization
    dictAccessPayload = {
        "organization": {
            "id": organizationInfo.id,
            "name": organizationInfo.name,
            "suspended_at": organizationInfo.suspendedAt,
            "deletion_requested_at": organizationInfo.deletionRequestedAt,
            "deletion_due_at": organizationInfo.deletionDueAt,
            "deletion_started_at": organizationInfo.deletionStartedAt,
        },
        "is_org_admin": accountAccessInfo.isOrgAdmin,
        "business_available": accountAccessInfo.businessAvailable,
        "departments": [
            {
                "id": departmentAccessInfo.id,
                "name": departmentAccessInfo.name,
                "path": departmentAccessInfo.path,
                "role": departmentAccessInfo.role,
            }
            for departmentAccessInfo in accountAccessInfo.departments
        ],
    }
    return AccountAccessResponse.model_validate(dictAccessPayload).model_dump(
        mode="python"
    )
