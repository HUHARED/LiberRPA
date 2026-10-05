# FileName: views.py
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
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.http import (
    DepartmentResourceListParameters,
    parse_department_resource_filters,
)
from organizations.models import Department
from organizations.permissions import AccessChannel, resolve_organization_access
from schedules.models import Schedule

from .contracts import (
    ExecutorUpdateRequest,
    ExecutorCreationRequest,
    ExecutorDeletionRequest,
    ExecutorDispatchRequest,
    ExecutorUnassociateRequest,
    ExecutorUpdateResponse,
    ExecutorListResponse,
    ExecutorDetailsResponse,
)
from .group_queries import get_executor_group_references
from .http import (
    get_executor_request_membership,
    lock_executor_write_access,
    build_executor_payload,
    build_executor_info_payload,
    build_executor_work_payload,
)
from .models import Executor
from .queries import get_executor_list, get_executor_details
from .services import (
    create_executor,
    update_executor,
    set_executor_dispatch,
    delete_executor,
    unassociate_executor,
)

_LOGGER = logging.getLogger("console.executors")
_INT_MAX_EXECUTOR_BODY_BYTES = 16 * 1024
_HANDLED_ERRORS = (
    SessionInvalidatedError,
    PermissionDenied,
    ValidationError,
    Executor.DoesNotExist,
    Department.DoesNotExist,
    InvalidPage,
    ContractValidationError,
    PydanticSerializationError,
    ImproperlyConfigured,
    DatabaseError,
)


class ExecutorListParameters(DepartmentResourceListParameters):
    dispatchStates: tuple[bool, ...]


def _build_executor_error_response(e: Exception) -> JsonResponse:
    match e:
        case SessionInvalidatedError():
            return build_authentication_required_response()
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
                "executor_work_reference",
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
        case ContractValidationError() | PydanticSerializationError():
            # Request parsing errors have already been handled before entering the write transaction.
            _LOGGER.exception("Invalid Executor response contract.")
            return build_error_response(
                "internal_server_error",
                "The service could not build a valid response.",
                statusCode=500,
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
            with transaction.atomic():
                access = lock_executor_write_access(request, membership)
                executor = create_executor(
                    access,
                    departmentId=executorRequest.department_id,
                    name=executorRequest.name,
                    notes=executorRequest.notes,
                )
                return JsonResponse(
                    ExecutorUpdateResponse.model_validate({
                        "executor": build_executor_payload(executor)
                    }).model_dump(mode="python"),
                    status=201,
                )

        listParametersResult = _get_list_parameters(request)
        if isinstance(listParametersResult, JsonResponse):
            return listParametersResult
        access = resolve_organization_access(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
        )
        executorPage = get_executor_list(
            access,
            **listParametersResult,
        )
        dictListPayload = {
            "executors": [
                build_executor_info_payload(entry) for entry in executorPage.executors
            ],
            "page": executorPage.page,
            "page_size": executorPage.pageSize,
            "total_count": executorPage.totalCount,
            "total_pages": executorPage.totalPages,
        }
        return JsonResponse(
            ExecutorListResponse.model_validate(dictListPayload).model_dump(mode="python")
        )
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
            with transaction.atomic():
                access = lock_executor_write_access(request, membership)
                executor = update_executor(
                    access,
                    executorId=executorId,
                    name=executorRequest.name,
                    notes=executorRequest.notes,
                )
                return JsonResponse(
                    ExecutorUpdateResponse.model_validate({
                        "executor": build_executor_payload(executor)
                    }).model_dump(mode="python")
                )
        details = get_executor_details(
            actorId=membership.user_id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            executorId=executorId,
        )
        dictDetailsPayload = {
            "executor": {
                **build_executor_info_payload(details),
                **build_executor_work_payload(details),
                "executor_groups": [
                    {"id": group.id, "name": group.name}
                    for group in get_executor_group_references(details.executor)
                ],
                "referencing_schedules": list(
                    Schedule.objects
                    .filter(
                        department_id=details.executor.department_id,
                        deleted_at__isnull=True,
                        executor_ids__contains=[str(details.executor.pk)],
                    )
                    .order_by("name", "id")
                    .values("id", "name", "enabled")
                ),
            }
        }
        return JsonResponse(
            ExecutorDetailsResponse.model_validate(dictDetailsPayload).model_dump(
                mode="python"
            )
        )
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
        with transaction.atomic():
            access = lock_executor_write_access(request, membership)
            executor = set_executor_dispatch(
                access,
                executorId=executorId,
                dispatchEnabled=dispatchRequest.dispatch_enabled,
            )
            return JsonResponse(
                ExecutorUpdateResponse.model_validate({
                    "executor": build_executor_payload(executor)
                }).model_dump(mode="python")
            )
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
        with transaction.atomic():
            access = lock_executor_write_access(request, membership)
            executor = delete_executor(access, executorId=executorId)
            return JsonResponse(
                ExecutorUpdateResponse.model_validate({
                    "executor": build_executor_payload(executor)
                }).model_dump(mode="python")
            )
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
        with transaction.atomic():
            access = lock_executor_write_access(request, membership)
            executor = unassociate_executor(
                access,
                executorId=executorId,
                expectedSessionId=unassociateRequest.session_id,
            )
            return JsonResponse(
                ExecutorUpdateResponse.model_validate({
                    "executor": build_executor_payload(executor)
                }).model_dump(mode="python")
            )
    except _HANDLED_ERRORS as e:
        return _build_executor_error_response(e)
