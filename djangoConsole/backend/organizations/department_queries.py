# FileName: department_queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from .models import Department, DepartmentRole, DepartmentMembership
from .validators import path_name_key
from .permissions import (
    AccessChannel,
    require_organization_admin,
    resolve_organization_access,
)


@dataclass(frozen=True)
class DepartmentInfo:
    id: uuid.UUID
    name: str
    parentId: uuid.UUID | None
    path: str
    notes: str


@dataclass(frozen=True)
class DepartmentMemberInfo:
    userId: uuid.UUID
    email: str
    username: str
    role: DepartmentRole


@dataclass(frozen=True)
class DepartmentDetailsInfo:
    department: DepartmentInfo
    members: tuple[DepartmentMemberInfo, ...]


def get_department_tree(organizationId: uuid.UUID) -> dict[uuid.UUID, Department]:
    """Load active departments for one operation; this is not an authorization check."""
    return Department.objects.filter(
        organization_id=organizationId, deleted_at__isnull=True
    ).in_bulk()


def resolve_department_path(
    pathParts: tuple[str, ...], departmentsById: Mapping[uuid.UUID, Department]
) -> Department:
    """Resolve validated segments in one loaded tree; callers authorize the target separately."""
    parentId = None
    department = None
    for part in pathParts:
        partKey = path_name_key(part)
        matches = [
            entry
            for entry in departmentsById.values()
            if entry.parent_id == parentId and entry.name_key == partKey
        ]
        if len(matches) != 1:
            raise Department.DoesNotExist
        department = matches[0]
        parentId = department.pk
    if department is None:
        raise Department.DoesNotExist
    return department


def get_department_path(
    department: Department, departmentsById: Mapping[uuid.UUID, Department]
) -> str:
    """Derive a display path from the already loaded organization tree."""
    listDepartmentName = [department.name]
    parentId = department.parent_id
    # Department write services enforce a valid tree within one organization.
    while parentId is not None:
        parentDepartment = departmentsById[parentId]
        listDepartmentName.append(parentDepartment.name)
        parentId = parentDepartment.parent_id
    return "/".join(reversed(listDepartmentName))


def _get_admin_department_tree(
    actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> dict[uuid.UUID, Department]:
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    require_organization_admin(access)
    return get_department_tree(access.organization.pk)


def _build_department_info(
    department: Department, departmentsById: Mapping[uuid.UUID, Department]
) -> DepartmentInfo:
    return DepartmentInfo(
        id=department.id,
        name=department.name,
        parentId=department.parent_id,
        path=get_department_path(department, departmentsById),
        notes=department.notes,
    )


def get_department_list(
    *, actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> list[DepartmentInfo]:
    """Return the active tree for organization administration, ordered by full path."""
    dictDepartmentById = _get_admin_department_tree(actorId, organizationId, channel)
    listDepartmentInfo = [
        _build_department_info(department, dictDepartmentById)
        for department in dictDepartmentById.values()
    ]
    return sorted(
        listDepartmentInfo,
        key=lambda departmentInfo: (
            path_name_key(departmentInfo.path),
            departmentInfo.id,
        ),
    )


def get_department_details(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    departmentId: uuid.UUID,
) -> DepartmentDetailsInfo:
    """Return one active department and its explicit current membership assignments."""
    dictDepartmentById = _get_admin_department_tree(actorId, organizationId, channel)
    department = dictDepartmentById.get(departmentId)
    if department is None:
        raise Department.DoesNotExist

    # An organization administrator without an explicit department role is not a row here.
    listDepartmentMemberInfo = [
        DepartmentMemberInfo(
            userId=userId, email=email, username=username, role=DepartmentRole(role)
        )
        for userId, email, username, role in DepartmentMembership.objects.filter(
            department=department, membership__organization_id=organizationId
        ).values_list(
            "membership_id",
            "membership__user__email",
            "membership__user__username",
            "role",
        )
    ]
    return DepartmentDetailsInfo(
        department=_build_department_info(department, dictDepartmentById),
        members=tuple(
            sorted(
                listDepartmentMemberInfo,
                key=lambda memberInfo: (
                    memberInfo.username.casefold(),
                    memberInfo.email,
                    memberInfo.userId,
                ),
            )
        ),
    )
