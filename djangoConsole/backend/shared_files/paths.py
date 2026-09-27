# FileName: paths.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import PermissionDenied, ValidationError

from organizations.department_queries import get_department_path
from organizations.models import Department, DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)
from organizations.validators import (
    path_name_key as name_key,
    normalize_path_name as normalize_name,
)


def path_parts(value: str, *, department: bool = False) -> list[str]:
    value = value.replace("\\", "/")
    if department:
        value = value.removesuffix("/")
    parts = value.removeprefix("/").split("/")
    if len(parts) < (1 if department else 2) or len(parts) > 65:
        raise ValidationError("Use a full department path and file name.")
    return [normalize_name(part) for part in parts]


def require_department(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> Department:
    try:
        return get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ).get(pk=departmentId)
    except Department.DoesNotExist:
        raise PermissionDenied("The department is unavailable.") from None


def resolve_department(access: OrganizationAccessContext, parts: list[str]) -> Department:
    # Existing department tables predate normalized keys. Compare only this organization's tree.
    departments = list(
        Department.objects.filter(
            organization=access.organization, deleted_at__isnull=True
        )
    )
    parentId = None
    department = None
    for part in parts:
        matches = [
            entry
            for entry in departments
            if entry.parent_id == parentId and name_key(entry.name) == name_key(part)
        ]
        if len(matches) != 1:
            raise Department.DoesNotExist
        department = matches[0]
        parentId = department.pk
    if department is None:
        raise Department.DoesNotExist
    return require_department(access, department.pk)


def department_path(department: Department) -> str:
    tree = Department.objects.filter(
        organization_id=department.organization_id, deleted_at__isnull=True
    ).in_bulk()
    return "/" + get_department_path(department, tree)
