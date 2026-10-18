# FileName: access.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import PermissionDenied

from organizations.contracts import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)


def require_executor_management(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> None:
    if (
        not get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER)
        .filter(pk=departmentId)
        .exists()
    ):
        raise PermissionDenied(
            "Developer access is required to manage Executors and groups."
        )
