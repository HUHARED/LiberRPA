# FileName: views.py
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

from .group_queries import get_executor_group_references
from .http import (
    build_executor_info_payload,
    build_executor_payload,
    get_executor_request_membership,
    get_executor_write_context,
)
from .models import Executor
from .queries import get_executor_details, get_executor_list
from .services import (
    create_executor,
    delete_executor,
    set_executor_dispatch,
    unassociate_executor,
    update_executor,
)

_INT_MAX_EXECUTOR_BODY_BYTES = 16 * 1024
_HANDLED_ERRORS = (
    SessionInvalidatedError,
    PermissionDenied,
    ValidationError,
    Executor.DoesNotExist,
    Department.DoesNotExist,
    InvalidPage,
    ImproperlyConfigured,
    DatabaseError,
)


class ExecutorUpdateRequest(JsonRequest):
    name: str
    notes: str


class ExecutorCreationRequest(ExecutorUpdateRequest):
    department_id: Annotated[uuid.UUID, Field(strict=False)]
    notes: str = ""


class ExecutorDispatchRequest(JsonRequest):
    dispatch_enabled: bool


class ExecutorDeletionRequest(JsonRequest):
    """The URL supplies the ID; the server checks current authorization and dependencies."""


class ExecutorUnassociateRequest(JsonRequest):
    session_id: Annotated[uuid.UUID, Field(strict=False)]


class ExecutorListParameters(DepartmentResourceListParameters):
    dispatchStates: tuple[bool, ...]


def _build_executor_error_response(e: Exception) -> JsonResponse:
    match e:
        case SessionInvalidatedError():
            return build_error_response(
                "authentication_required", "Sign in again to continue.", statusCode=401
            )
        case PermissionDenied():
            return build_error_response(
                "executor_access_required",
                "Executor access is unavailable.",
                statusCode=403,
            )
        case Executor.DoesNotExist() | Department.DoesNotExist():
            return build_error_response(
                "executor_not_found",
                "The executor or department is unavailable.",
                statusCode=404,
            )
        case InvalidPage():
            return build_error_response(
                "invalid_page", "The requested page is unavailable.", statusCode=400
            )
        case ValidationError():
            strErrorCode = getattr(e, "code", None)
            if strErrorCode in (
                "executor_count_limit",
                "executor_association_changed",
                "executor_group_reference",
            ):
                return build_error_response(strErrorCode, e.messages[0], statusCode=409)
            boolDuplicateNameFound = any(
                fieldError.code == "duplicate_executor_name"
                for listFieldError in getattr(e, "error_dict", {}).values()
                for fieldError in listFieldError
            )
            return build_error_response(
                "duplicate_executor_name"
                if boolDuplicateNameFound
                else "invalid_executor",
                "Some executor fields are invalid.",
                statusCode=409 if boolDuplicateNameFound else 400,
                fields=e.message_dict
                if hasattr(e, "error_dict")
                else {"__all__": e.messages},
            )
        case _:
            return build_service_unavailable_response()


def _get_list_parameters(request: HttpRequest) -> ExecutorListParameters | JsonResponse:
    try:
        dictListParameter = parse_department_resource_filters(
            request.GET, extraFields=frozenset({"dispatch_enabled"})
        )
        listDispatchValue = request.GET.getlist("dispatch_enabled")
        if len(listDispatchValue) > 2:
            raise ValueError
        dictDispatchValue = {"true": True, "false": False}
        return {
            **dictListParameter,
            "dispatchStates": tuple(
                dictDispatchValue[strDispatchValue]
                for strDispatchValue in listDispatchValue
            ),
        }
    except (ValueError, KeyError):
        return build_error_response(
            "invalid_filter",
            "Use one positive page, one name, department UUIDs, and true/false dispatch values.",
            statusCode=400,
        )


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_variables()
def list_or_create_executors(request: HttpRequest) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        if request.method == "POST":
            executorRequest = parse_json_request(
                request,
                ExecutorCreationRequest,
                maxBodyBytes=_INT_MAX_EXECUTOR_BODY_BYTES,
            )
            if isinstance(executorRequest, JsonResponse):
                return executorRequest
            executor = create_executor(
                **get_executor_write_context(request, membership),
                departmentId=executorRequest.department_id,
                name=executorRequest.name,
                notes=executorRequest.notes,
            )
            return JsonResponse(
                {"executor": build_executor_payload(executor)}, status=201
            )

        dictListParameter = _get_list_parameters(request)
        if isinstance(dictListParameter, JsonResponse):
            return dictListParameter
        executorPage = get_executor_list(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            **dictListParameter,
        )
        return JsonResponse({
            "executors": [
                build_executor_info_payload(entry) for entry in executorPage.executors
            ],
            "page": executorPage.page,
            "page_size": executorPage.pageSize,
            "total_count": executorPage.totalCount,
            "total_pages": executorPage.totalPages,
        })
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_variables()
def get_or_update_executor(request: HttpRequest, executorId: uuid.UUID) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        if request.method == "POST":
            executorRequest = parse_json_request(
                request, ExecutorUpdateRequest, maxBodyBytes=_INT_MAX_EXECUTOR_BODY_BYTES
            )
            if isinstance(executorRequest, JsonResponse):
                return executorRequest
            executor = update_executor(
                **get_executor_write_context(request, membership),
                executorId=executorId,
                name=executorRequest.name,
                notes=executorRequest.notes,
            )
            return JsonResponse({"executor": build_executor_payload(executor)})
        details = get_executor_details(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            executorId=executorId,
        )
        return JsonResponse({
            "executor": {
                **build_executor_info_payload(details),
                "executor_groups": [
                    {"id": group.id, "name": group.name}
                    for group in get_executor_group_references(details.executor)
                ],
            }
        })
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def change_executor_dispatch(request: HttpRequest, executorId: uuid.UUID) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        dispatchRequest = parse_json_request(request, ExecutorDispatchRequest)
        if isinstance(dispatchRequest, JsonResponse):
            return dispatchRequest
        executor = set_executor_dispatch(
            **get_executor_write_context(request, membership),
            executorId=executorId,
            dispatchEnabled=dispatchRequest.dispatch_enabled,
        )
        return JsonResponse({"executor": build_executor_payload(executor)})
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def delete_executor_record(request: HttpRequest, executorId: uuid.UUID) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        deletionRequest = parse_json_request(request, ExecutorDeletionRequest)
        if isinstance(deletionRequest, JsonResponse):
            return deletionRequest
        executor = delete_executor(
            **get_executor_write_context(request, membership), executorId=executorId
        )
        return JsonResponse({"executor": build_executor_payload(executor)})
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def unassociate_executor_record(
    request: HttpRequest, executorId: uuid.UUID
) -> JsonResponse:
    try:
        membership = get_executor_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        unassociateRequest = parse_json_request(request, ExecutorUnassociateRequest)
        if isinstance(unassociateRequest, JsonResponse):
            return unassociateRequest
        executor = unassociate_executor(
            **get_executor_write_context(request, membership),
            executorId=executorId,
            expectedSessionId=unassociateRequest.session_id,
        )
        return JsonResponse({"executor": build_executor_payload(executor)})
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)
