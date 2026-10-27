# FileName: group_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from accounts.session_revocation import SessionInvalidatedError
from console_project.contracts import MessageResponse
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.http import (
    DepartmentResourceListParameters,
    get_request_membership,
    lock_request_write_access,
    parse_department_resource_filters,
)
from organizations.models import Department
from organizations.permissions import AccessChannel, build_organization_access

from .contracts import (
    ExecutorGroupUpdateRequest,
    ExecutorGroupCreationRequest,
    ExecutorGroupDeletionRequest,
    ExecutorGroupWriteEntryResponse,
    ExecutorGroupWarningResponse,
    ExecutorGroupWriteResponse,
)
from .group_queries import (
    get_executor_group_list,
    get_executor_group_details,
)
from .group_services import (
    ExecutorGroupWriteResult,
    create_executor_group,
    update_executor_group,
    delete_executor_group,
)
from .models import ExecutorGroup

_LOGGER = logging.getLogger("console.executor_groups")
_INT_MAX_GROUP_BODY_BYTES = 64 * 1024
_HANDLED_GROUP_ERRORS = (
    SessionInvalidatedError,
    PermissionDenied,
    ValidationError,
    ExecutorGroup.DoesNotExist,
    Department.DoesNotExist,
    InvalidPage,
    ContractValidationError,
    PydanticSerializationError,
    ImproperlyConfigured,
    DatabaseError,
)


def _build_group_write_response(
    result: ExecutorGroupWriteResult,
) -> ExecutorGroupWriteResponse:
    group = result.group
    return ExecutorGroupWriteResponse(
        executor_group=ExecutorGroupWriteEntryResponse(
            id=group.id,
            name=group.name,
            department_id=group.department_id,
            notes=group.notes,
            created_at=group.created_at,
            executor_ids=list(result.executorIds),
            member_count=len(result.executorIds),
            is_empty=not result.executorIds,
        ),
        warnings=[]
        if result.executorIds
        else [
            ExecutorGroupWarningResponse(
                code="empty_executor_group",
                message="This group has no members. Add Executors before using it for execution.",
            )
        ],
    )


def _build_group_error_response(e: Exception) -> JsonResponse:
    match e:
        case SessionInvalidatedError():
            return build_authentication_required_response()
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
            strCode = getattr(e, "code", None)
            if strCode is not None and strCode in (
                "executor_group_count_limit",
                "executor_group_work_reference",
            ):
                return build_error_response(strCode, e.messages[0], statusCode=409)
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
        case ContractValidationError() | PydanticSerializationError():
            # Request parsing errors have already been handled before entering the write transaction.
            _LOGGER.exception("Invalid Executor group response contract.")
            return build_error_response(
                "internal_server_error",
                "The service could not build a valid response.",
                statusCode=500,
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
        membership = get_request_membership(request)
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
            with transaction.atomic():
                access = lock_request_write_access(request, membership)
                result = create_executor_group(
                    access,
                    departmentId=groupRequest.department_id,
                    name=groupRequest.name,
                    notes=groupRequest.notes,
                    executorIds=tuple(groupRequest.executor_ids),
                )
                return JsonResponse(
                    _build_group_write_response(result).model_dump(mode="python"),
                    status=201,
                )
        listParametersResult = _get_list_parameters(request)
        if isinstance(listParametersResult, JsonResponse):
            return listParametersResult
        response = get_executor_group_list(
            access=build_organization_access(membership, channel=AccessChannel.SESSION),
            **listParametersResult,
        )
        return JsonResponse(response.model_dump(mode="python"))
    except _HANDLED_GROUP_ERRORS as e:
        return _build_group_error_response(e)


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_variables()
def get_or_update_executor_group(
    request: HttpRequest, groupId: uuid.UUID
) -> JsonResponse:
    try:
        membership = get_request_membership(request)
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
            with transaction.atomic():
                access = lock_request_write_access(request, membership)
                result = update_executor_group(
                    access,
                    groupId=groupId,
                    name=groupRequest.name,
                    notes=groupRequest.notes,
                    executorIds=tuple(groupRequest.executor_ids),
                )
                return JsonResponse(
                    _build_group_write_response(result).model_dump(mode="python")
                )
        response = get_executor_group_details(
            access=build_organization_access(membership, channel=AccessChannel.SESSION),
            groupId=groupId,
        )
        return JsonResponse(response.model_dump(mode="python"))
    except _HANDLED_GROUP_ERRORS as e:
        return _build_group_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def delete_executor_group_record(
    request: HttpRequest, groupId: uuid.UUID
) -> JsonResponse:
    try:
        membership = get_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        deletionRequest = parse_json_request(request, ExecutorGroupDeletionRequest)
        if isinstance(deletionRequest, JsonResponse):
            return deletionRequest
        with transaction.atomic():
            access = lock_request_write_access(request, membership)
            delete_executor_group(access, groupId=groupId)
            return JsonResponse(
                MessageResponse(message="Executor group deleted.").model_dump(
                    mode="python"
                )
            )
    except _HANDLED_GROUP_ERRORS as e:
        return _build_group_error_response(e)
