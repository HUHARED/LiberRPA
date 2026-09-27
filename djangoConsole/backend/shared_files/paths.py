# FileName: paths.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import PermissionDenied, ValidationError

from organizations.models import Department, DepartmentRole
from organizations.department_queries import get_department_path
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)
from organizations.validators import path_name_key, normalize_path_name


def parse_file_path(value: str, *, departmentOnly: bool = False) -> tuple[str, ...]:
    """Normalize and validate once at the HTTP boundary, before taking business locks."""
    value = value.replace("\\", "/")
    if departmentOnly:
        value = value.removesuffix("/")
    parts = value.removeprefix("/").split("/")
    if len(parts) < (1 if departmentOnly else 2) or len(parts) > 65:
        raise ValidationError("Use a full department path and file name.")
    return tuple(normalize_path_name(part) for part in parts)


def load_department_tree(organizationId: uuid.UUID) -> dict[uuid.UUID, Department]:
    return Department.objects.filter(
        organization_id=organizationId, deleted_at__isnull=True
    ).in_bulk()


def require_department(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> Department:
    try:
        return get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ).get(pk=departmentId)
    except Department.DoesNotExist:
        raise PermissionDenied("The department is unavailable.") from None


def resolve_department(
    parts: tuple[str, ...], departmentsById: dict[uuid.UUID, Department]
) -> Department:
    """Resolve a logical path in a loaded tree; callers must authorize the target department."""
    parentId = None
    department = None
    for part in parts:
        partKey = path_name_key(part)
        matches = [
            entry
            for entry in departmentsById.values()
            if entry.parent_id == parentId and path_name_key(entry.name) == partKey
        ]
        if len(matches) != 1:
            raise Department.DoesNotExist
        department = matches[0]
        parentId = department.pk
    if department is None:
        raise Department.DoesNotExist
    return department


def build_department_path(
    department: Department, departmentsById: dict[uuid.UUID, Department]
) -> str:
    return "/" + get_department_path(department, departmentsById)
