# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from .access import AccountAccessInfo


def build_account_access_payload(
    accountAccessInfo: AccountAccessInfo,
) -> dict[str, object]:
    """Map internal access attributes to the shared HTTP response fields."""
    organizationInfo = accountAccessInfo.organization
    return {
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
