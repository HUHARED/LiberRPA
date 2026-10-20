# FileName: department_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid
from typing import cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)

from .contracts import (
    DepartmentUpdateRequest,
    DepartmentCreationRequest,
    DepartmentDeletionRequest,
    DepartmentWriteResponse,
    DepartmentListResponse,
    DepartmentDetailsResponse,
    DepartmentDeletionPreviewResponse,
    DepartmentDeletionResponse,
)
from .models import Department
from .http import lock_request_write_access
from .permissions import AccessChannel, get_current_membership
from .rate_limits import check_request_budget
from .department_queries import (
    DepartmentInfo,
    get_department_list,
    get_department_details,
)
from .department_services import create_department, update_department
from .department_deletion import (
    DepartmentDeletionInfo,
    DepartmentDeletionBlockedError,
    get_department_deletion_info,
    delete_department,
)

_LOGGER = logging.getLogger("console.departments")
_INT_MAX_DEPARTMENT_BODY_BYTES = 32 * 1024


def _build_department_payload(departmentInfo: DepartmentInfo) -> dict[str, object]:
    return {
        "id": departmentInfo.id,
        "name": departmentInfo.name,
        "parent_id": departmentInfo.parentId,
        "path": departmentInfo.path,
        "notes": departmentInfo.notes,
    }


def _build_saved_department_response(
    department: Department, *, statusCode: int
) -> JsonResponse:
    # Serialize the saved fields without additional queries, still inside the caller's transaction.
    return JsonResponse(
        DepartmentWriteResponse.model_validate({
            "department": {
                "id": department.id,
                "name": department.name,
                "parent_id": department.parent_id,
                "notes": department.notes,
            }
        }).model_dump(mode="python"),
        status=statusCode,
    )


def _build_department_validation_response(
    validationError: ValidationError,
) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        dictFieldMessage: dict[str, list[str]] = {}
        boolDuplicateNameFound = False
        for strFieldName, listFieldError in validationError.error_dict.items():
            for fieldError in listFieldError:
                boolDuplicateName = fieldError.code == "duplicate_department_name"
                boolDuplicateNameFound = boolDuplicateNameFound or boolDuplicateName
                strResponseFieldName = (
                    "name"
                    if boolDuplicateName
                    else "parent_id"
                    if strFieldName == "parent"
                    else strFieldName
                )
                dictFieldMessage.setdefault(strResponseFieldName, []).extend(
                    fieldError.messages
                )
        return build_error_response(
            "duplicate_department_name"
            if boolDuplicateNameFound
            else "invalid_department",
            "Some department fields are invalid.",
            statusCode=409 if boolDuplicateNameFound else 400,
            fields=dictFieldMessage,
        )

    strErrorCode = validationError.error_list[0].code or "invalid_department"
    return build_error_response(
        strErrorCode,
        " ".join(validationError.messages),
        statusCode=409 if strErrorCode == "department_count_limit" else 400,
    )


def _build_department_response_error() -> JsonResponse:
    _LOGGER.exception("Could not build a valid department response.")
    return build_error_response(
        "internal_server_error",
        "The service could not build a valid response.",
        statusCode=500,
    )


@never_cache
@require_http_methods(["GET", "POST"])
def list_or_create_departments(request: HttpRequest) -> JsonResponse:
    """Read the department tree or create a department with administrator permission."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        check_request_budget(request, membership.organization)
        if request.method == "POST":
            departmentRequest = parse_json_request(
                request,
                DepartmentCreationRequest,
                maxBodyBytes=_INT_MAX_DEPARTMENT_BODY_BYTES,
            )
            if isinstance(departmentRequest, JsonResponse):
                return departmentRequest
            with transaction.atomic():
                access = lock_request_write_access(request, membership)
                department = create_department(
                    access=access,
                    name=departmentRequest.name,
                    parentId=departmentRequest.parent_id,
                    notes=departmentRequest.notes,
                )
                return _build_saved_department_response(department, statusCode=201)

        listDepartmentInfo = get_department_list(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
        )
        dictListPayload = {
            "departments": [
                _build_department_payload(departmentInfo)
                for departmentInfo in listDepartmentInfo
            ]
        }
        return JsonResponse(
            DepartmentListResponse.model_validate(dictListPayload).model_dump(
                mode="python"
            )
        )
    except ValidationError as e:
        return _build_department_validation_response(e)
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except PermissionDenied:
        return build_error_response(
            "department_access_required",
            "Department administration is unavailable.",
            statusCode=403,
        )
    except (ContractValidationError, PydanticSerializationError):
        return _build_department_response_error()
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_department(
    request: HttpRequest, departmentId: uuid.UUID
) -> JsonResponse:
    """Read or edit one current department without changing its stable identity."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        check_request_budget(request, membership.organization)
        if request.method == "POST":
            departmentRequest = parse_json_request(
                request,
                DepartmentUpdateRequest,
                maxBodyBytes=_INT_MAX_DEPARTMENT_BODY_BYTES,
            )
            if isinstance(departmentRequest, JsonResponse):
                return departmentRequest
            with transaction.atomic():
                access = lock_request_write_access(request, membership)
                department = update_department(
                    access=access,
                    departmentId=departmentId,
                    name=departmentRequest.name,
                    parentId=departmentRequest.parent_id,
                    notes=departmentRequest.notes,
                )
                return _build_saved_department_response(department, statusCode=200)

        detailsInfo = get_department_details(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            departmentId=departmentId,
        )
        dictDetailsPayload = {
            "department": _build_department_payload(detailsInfo.department),
            "members": [
                {
                    "user": {
                        "id": memberInfo.userId,
                        "email": memberInfo.email,
                        "username": memberInfo.username,
                    },
                    "role": memberInfo.role,
                }
                for memberInfo in detailsInfo.members
            ],
        }
        return JsonResponse(
            DepartmentDetailsResponse.model_validate(dictDetailsPayload).model_dump(
                mode="python"
            )
        )
    except ValidationError as e:
        return _build_department_validation_response(e)
    except Department.DoesNotExist:
        return build_error_response(
            "department_not_found", "Department not found or unavailable.", statusCode=404
        )
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except PermissionDenied:
        return build_error_response(
            "department_access_required",
            "Department administration is unavailable.",
            statusCode=403,
        )
    except (ContractValidationError, PydanticSerializationError):
        return _build_department_response_error()
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_delete_department(
    request: HttpRequest, departmentId: uuid.UUID
) -> JsonResponse:
    """Preview current deletion blockers or submit a fresh deletion attempt."""

    def build_deletion_payload(
        deletionInfo: DepartmentDeletionInfo,
    ) -> dict[str, object]:
        return DepartmentDeletionPreviewResponse.model_validate({
            "department": {
                "id": deletionInfo.departmentId,
                "name": deletionInfo.departmentName,
            },
            "can_delete": deletionInfo.canDelete,
            "blockers": [
                {"code": blocker.code, "count": blocker.count}
                for blocker in deletionInfo.blockers
            ],
        }).model_dump(mode="python")

    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        check_request_budget(request, membership.organization)
        if request.method == "POST":
            deletionRequest = parse_json_request(request, DepartmentDeletionRequest)
            if isinstance(deletionRequest, JsonResponse):
                return deletionRequest
            try:
                with transaction.atomic():
                    access = lock_request_write_access(request, membership)
                    department = delete_department(
                        access=access,
                        departmentId=departmentId,
                    )
                    return JsonResponse(
                        DepartmentDeletionResponse.model_validate({
                            "department": {
                                "id": department.id,
                                "name": department.name,
                                "deleted_at": department.deleted_at,
                            }
                        }).model_dump(mode="python")
                    )
            except DepartmentDeletionBlockedError as e:
                return JsonResponse(
                    {
                        **build_deletion_payload(e.deletionInfo),
                        "error": {
                            "code": "department_deletion_blocked",
                            "message": (
                                "Remove the remaining dependencies "
                                "before deleting this department."
                            ),
                        },
                    },
                    status=409,
                )

        deletionInfo = get_department_deletion_info(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            departmentId=departmentId,
        )
        return JsonResponse(build_deletion_payload(deletionInfo))
    except Department.DoesNotExist:
        return build_error_response(
            "department_not_found", "Department not found or unavailable.", statusCode=404
        )
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except PermissionDenied:
        return build_error_response(
            "department_access_required",
            "Department administration is unavailable.",
            statusCode=403,
        )
    except (ContractValidationError, PydanticSerializationError):
        return _build_department_response_error()
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
