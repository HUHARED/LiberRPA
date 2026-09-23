# FileName: group_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import Annotated

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST
from pydantic import Field

from accounts.session_revocation import SessionInvalidatedError
from console_project.http import (
    JsonRequest,
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.http import (
    DepartmentResourceListParameters,
    parse_department_resource_filters,
)
from organizations.models import Department
from organizations.permissions import AccessChannel

from .group_queries import (
    ExecutorGroupInfo,
    get_executor_group_details,
    get_executor_group_list,
)
from .group_services import (
    ExecutorGroupWriteResult,
    create_executor_group,
    delete_executor_group,
    update_executor_group,
)
from .http import (
    build_executor_info_payload,
    get_executor_request_membership,
    get_executor_write_context,
)
from .models import ExecutorGroup

_INT_MAX_GROUP_BODY_BYTES = 64 * 1024
_HANDLED_GROUP_ERRORS = (
    SessionInvalidatedError,
    PermissionDenied,
    ValidationError,
    ExecutorGroup.DoesNotExist,
    Department.DoesNotExist,
    InvalidPage,
    ImproperlyConfigured,
    DatabaseError,
)


class ExecutorGroupUpdateRequest(JsonRequest):
    name: str
    notes: str
    executor_ids: list[Annotated[uuid.UUID, Field(strict=False)]]


class ExecutorGroupCreationRequest(ExecutorGroupUpdateRequest):
    department_id: Annotated[uuid.UUID, Field(strict=False)]
    notes: str = ""
    executor_ids: list[Annotated[uuid.UUID, Field(strict=False)]] = Field(
        default_factory=list
    )


class ExecutorGroupDeletionRequest(JsonRequest):
    """The URL supplies the group identity; request data cannot bypass reference checks."""


def _build_group_payload(group: ExecutorGroup) -> dict[str, object]:
    return {
        "id": group.id,
        "name": group.name,
        "department_id": group.department_id,
        "notes": group.notes,
        "created_at": group.created_at,
        "deleted_at": group.deleted_at,
    }


def _build_group_info_payload(info: ExecutorGroupInfo) -> dict[str, object]:
    return {
        **_build_group_payload(info.group),
        "department": {
            "id": info.group.department_id,
            "name": info.group.department.name,
            "path": info.departmentPath,
        },
        "can_manage": info.canManage,
        "member_count": info.memberCount,
        "online_count": info.onlineCount,
        "is_empty": info.memberCount == 0,
    }


def _build_group_write_payload(result: ExecutorGroupWriteResult) -> dict[str, object]:
    return {
        "executor_group": {
            **_build_group_payload(result.group),
            "executor_ids": result.executorIds,
            "member_count": len(result.executorIds),
            "is_empty": not result.executorIds,
        },
        "warnings": []
        if result.executorIds
        else [
            {
                "code": "empty_executor_group",
                "message": "This group has no members. Add Executors before using it for execution.",
            }
        ],
    }


def _build_group_error_response(e: Exception) -> JsonResponse:
    match e:
        case SessionInvalidatedError():
            return build_error_response(
                "authentication_required", "Sign in again to continue.", statusCode=401
            )
        case PermissionDenied():
            return build_error_response(
                "executor_group_access_required",
                "Executor group access is unavailable.",
                statusCode=403,
            )
        case ExecutorGroup.DoesNotExist() | Department.DoesNotExist():
            return build_error_response(
                "executor_group_not_found",
                "The group or department is unavailable.",
                statusCode=404,
            )
        case InvalidPage():
            return build_error_response(
                "invalid_page", "The requested page is unavailable.", statusCode=400
            )
        case ValidationError():
            if getattr(e, "code", None) == "executor_group_count_limit":
                return build_error_response(
                    "executor_group_count_limit", e.messages[0], statusCode=409
                )
            boolDuplicateNameFound = any(
                fieldError.code == "duplicate_executor_group_name"
                for listFieldError in getattr(e, "error_dict", {}).values()
                for fieldError in listFieldError
            )
            return build_error_response(
                "duplicate_executor_group_name"
                if boolDuplicateNameFound
                else "invalid_executor_group",
                "Some Executor group fields are invalid.",
                statusCode=409 if boolDuplicateNameFound else 400,
                fields=e.message_dict
                if hasattr(e, "error_dict")
                else {"__all__": e.messages},
            )
        case _:
            return build_service_unavailable_response()


def _get_list_parameters(
    request: HttpRequest,
) -> DepartmentResourceListParameters | JsonResponse:
    try:
        return parse_department_resource_filters(request.GET)
    except ValueError:
        return build_error_response(
            "invalid_filter",
            "Use one positive page, one name, and department UUIDs.",
            statusCode=400,
        )


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_variables()
def list_or_create_executor_groups(request: HttpRequest) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        if request.method == "POST":
            groupRequest = parse_json_request(
                request,
                ExecutorGroupCreationRequest,
                maxBodyBytes=_INT_MAX_GROUP_BODY_BYTES,
            )
            if isinstance(groupRequest, JsonResponse):
                return groupRequest
            result = create_executor_group(
                **get_executor_write_context(request, membership),
                departmentId=groupRequest.department_id,
                name=groupRequest.name,
                notes=groupRequest.notes,
                executorIds=tuple(groupRequest.executor_ids),
            )
            return JsonResponse(_build_group_write_payload(result), status=201)
        dictListParameter = _get_list_parameters(request)
        if isinstance(dictListParameter, JsonResponse):
            return dictListParameter
        page = get_executor_group_list(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            **dictListParameter,
        )
        return JsonResponse({
            "executor_groups": [_build_group_info_payload(info) for info in page.groups],
            "page": page.page,
            "page_size": page.pageSize,
            "total_count": page.totalCount,
            "total_pages": page.totalPages,
        })
    except _HANDLED_GROUP_ERRORS as e:
        return _build_group_error_response(e)


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_variables()
def get_or_update_executor_group(
    request: HttpRequest, groupId: uuid.UUID
) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        if request.method == "POST":
            groupRequest = parse_json_request(
                request,
                ExecutorGroupUpdateRequest,
                maxBodyBytes=_INT_MAX_GROUP_BODY_BYTES,
            )
            if isinstance(groupRequest, JsonResponse):
                return groupRequest
            result = update_executor_group(
                **get_executor_write_context(request, membership),
                groupId=groupId,
                name=groupRequest.name,
                notes=groupRequest.notes,
                executorIds=tuple(groupRequest.executor_ids),
            )
            return JsonResponse(_build_group_write_payload(result))
        details = get_executor_group_details(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            groupId=groupId,
        )
        return JsonResponse({
            "executor_group": {
                **_build_group_info_payload(details.info),
                "members": [
                    build_executor_info_payload(member) for member in details.members
                ],
            }
        })
    except _HANDLED_GROUP_ERRORS as e:
        return _build_group_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def delete_executor_group_record(
    request: HttpRequest, groupId: uuid.UUID
) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        deletionRequest = parse_json_request(request, ExecutorGroupDeletionRequest)
        if isinstance(deletionRequest, JsonResponse):
            return deletionRequest
        group = delete_executor_group(
            **get_executor_write_context(request, membership), groupId=groupId
        )
        return JsonResponse({"executor_group": _build_group_payload(group)})
    except _HANDLED_GROUP_ERRORS as e:
        return _build_group_error_response(e)
