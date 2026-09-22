# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime
from typing import Annotated, TypedDict, cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST
from pydantic import Field

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError
from console_project.http import JsonRequest, build_error_response, parse_json_request
from organizations.models import Department, Membership
from organizations.permissions import AccessChannel, get_current_membership

from .models import Executor
from .queries import ExecutorInfo, get_executor_details, get_executor_list
from .services import (
    create_executor,
    delete_executor,
    set_executor_dispatch,
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


class ExecutorWriteContext(TypedDict):
    actorId: uuid.UUID
    organizationId: uuid.UUID
    channel: AccessChannel
    sessionAuthHash: str
    sessionExpiresAt: datetime


class ExecutorListParameters(TypedDict):
    pageNumber: int
    departmentIds: tuple[uuid.UUID, ...]
    name: str
    dispatchStates: tuple[bool, ...]


def _get_request_membership(request: HttpRequest) -> Membership | JsonResponse:
    if not request.user.is_authenticated:
        return build_error_response(
            "authentication_required", "Sign in to continue.", statusCode=401
        )
    return get_current_membership(actorId=cast(User, request.user).id)


@sensitive_variables()
def _get_write_context(
    request: HttpRequest, membership: Membership
) -> ExecutorWriteContext:
    return {
        "actorId": membership.user_id,
        "organizationId": membership.organization_id,
        "channel": AccessChannel.SESSION,
        "sessionAuthHash": request.session.get(HASH_SESSION_KEY, ""),
        "sessionExpiresAt": request.session.get_expiry_date(),
    }


def _build_executor_payload(executor: Executor) -> dict[str, object]:
    return {
        "id": executor.id,
        "name": executor.name,
        "department_id": executor.department_id,
        "notes": executor.notes,
        "dispatch_enabled": executor.dispatch_enabled,
        "created_at": executor.created_at,
        "deleted_at": executor.deleted_at,
    }


def _build_executor_info_payload(executorInfo: ExecutorInfo) -> dict[str, object]:
    return {
        **_build_executor_payload(executorInfo.executor),
        "department": {
            "id": executorInfo.executor.department_id,
            "name": executorInfo.executor.department.name,
            "path": executorInfo.departmentPath,
        },
        "can_manage": executorInfo.canManage,
    }


def _build_executor_error_response(e: Exception) -> JsonResponse:
    match e:
        case SessionInvalidatedError():
            return build_error_response(
                "authentication_required", "Sign in again to continue.", statusCode=401
            )
        case PermissionDenied():
            return build_error_response(
                "executor_access_required", "Executor access is unavailable.", statusCode=403
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
            if getattr(e, "code", None) == "executor_count_limit":
                return build_error_response(
                    "executor_count_limit", e.messages[0], statusCode=409
                )
            hasDuplicateName = any(
                fieldError.code == "duplicate_executor_name"
                for listFieldError in getattr(e, "error_dict", {}).values()
                for fieldError in listFieldError
            )
            return JsonResponse(
                {
                    "error": {
                        "code": "duplicate_executor_name"
                        if hasDuplicateName else "invalid_executor",
                        "message": "Some executor fields are invalid.",
                        "fields": e.message_dict
                        if hasattr(e, "error_dict") else {"__all__": e.messages},
                    }
                },
                status=409 if hasDuplicateName else 400,
            )
        case _:
            return build_error_response(
                "service_unavailable", "The service is temporarily unavailable.", statusCode=503
            )


def _get_list_parameters(request: HttpRequest) -> ExecutorListParameters | JsonResponse:
    try:
        if set(request.GET) - {"page", "department_id", "name", "dispatch_enabled"}:
            raise ValueError
        if len(request.GET.getlist("page")) > 1 or len(request.GET.getlist("name")) > 1:
            raise ValueError
        pageValue = request.GET.get("page", "1")
        if (
            not pageValue.isascii()
            or not pageValue.isdecimal()
            or len(pageValue) > 9
            or int(pageValue) < 1
        ):
            raise ValueError
        name = request.GET.get("name", "").strip()
        departmentValues = request.GET.getlist("department_id")
        dispatchValues = request.GET.getlist("dispatch_enabled")
        if len(name) > 128 or len(departmentValues) > 100 or len(dispatchValues) > 2:
            raise ValueError
        dictDispatchValue = {"true": True, "false": False}
        return {
            "pageNumber": int(pageValue),
            "departmentIds": tuple(uuid.UUID(value) for value in departmentValues),
            "name": name,
            "dispatchStates": tuple(dictDispatchValue[value] for value in dispatchValues),
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
        membership = _get_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        if request.method == "POST":
            executorRequest = parse_json_request(
                request, ExecutorCreationRequest, maxBodyBytes=_INT_MAX_EXECUTOR_BODY_BYTES
            )
            if isinstance(executorRequest, JsonResponse):
                return executorRequest
            executor = create_executor(
                **_get_write_context(request, membership),
                departmentId=executorRequest.department_id,
                name=executorRequest.name,
                notes=executorRequest.notes,
            )
            return JsonResponse({"executor": _build_executor_payload(executor)}, status=201)

        parameters = _get_list_parameters(request)
        if isinstance(parameters, JsonResponse):
            return parameters
        executorPage = get_executor_list(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            **parameters,
        )
        return JsonResponse({
            "executors": [
                _build_executor_info_payload(entry) for entry in executorPage.executors
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
        membership = _get_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        if request.method == "POST":
            executorRequest = parse_json_request(
                request, ExecutorUpdateRequest, maxBodyBytes=_INT_MAX_EXECUTOR_BODY_BYTES
            )
            if isinstance(executorRequest, JsonResponse):
                return executorRequest
            executor = update_executor(
                **_get_write_context(request, membership),
                executorId=executorId,
                name=executorRequest.name,
                notes=executorRequest.notes,
            )
            return JsonResponse({"executor": _build_executor_payload(executor)})
        details = get_executor_details(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            executorId=executorId,
        )
        return JsonResponse({"executor": _build_executor_info_payload(details)})
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def change_executor_dispatch(request: HttpRequest, executorId: uuid.UUID) -> JsonResponse:
    try:
        membership = _get_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        dispatchRequest = parse_json_request(request, ExecutorDispatchRequest)
        if isinstance(dispatchRequest, JsonResponse):
            return dispatchRequest
        executor = set_executor_dispatch(
            **_get_write_context(request, membership),
            executorId=executorId,
            dispatchEnabled=dispatchRequest.dispatch_enabled,
        )
        return JsonResponse({"executor": _build_executor_payload(executor)})
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def delete_executor_record(request: HttpRequest, executorId: uuid.UUID) -> JsonResponse:
    try:
        membership = _get_request_membership(request)
        if isinstance(membership, JsonResponse):
            return membership
        deletionRequest = parse_json_request(request, ExecutorDeletionRequest)
        if isinstance(deletionRequest, JsonResponse):
            return deletionRequest
        executor = delete_executor(
            **_get_write_context(request, membership), executorId=executorId
        )
        return JsonResponse({"executor": _build_executor_payload(executor)})
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)
