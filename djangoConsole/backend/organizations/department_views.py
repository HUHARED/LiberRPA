# FileName: department_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import uuid
from typing import Annotated, cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from pydantic import Field

from accounts.models import User
from console_project.http import JsonRequest, build_error_response, parse_json_request

from .department_deletion import (
    DepartmentDeletionBlockedError,
    DepartmentDeletionInfo,
    delete_department,
    get_department_deletion_info,
)
from .department_queries import (
    DepartmentInfo,
    get_department_details,
    get_department_list,
)
from .models import Department
from .permissions import AccessChannel, get_current_membership
from .services import create_department, update_department

_INT_MAX_DEPARTMENT_BODY_BYTES = 32 * 1024

# JSON represents a UUID as text; other fields keep the shared strict type validation.
type ParentDepartmentId = Annotated[uuid.UUID, Field(strict=False)] | None


class DepartmentUpdateRequest(JsonRequest):
    name: str
    parent_id: ParentDepartmentId
    notes: str


class DepartmentCreationRequest(DepartmentUpdateRequest):
    parent_id: ParentDepartmentId = None
    notes: str = ""


class DepartmentDeletionRequest(JsonRequest):
    """The URL selects the department; the server resolves all deletion conditions."""


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
    # Return the saved fields without additional queries after the write commits.
    return JsonResponse(
        {
            "department": {
                "id": department.id,
                "name": department.name,
                "parent_id": department.parent_id,
                "notes": department.notes,
            }
        },
        status=statusCode,
    )


def _build_department_validation_response(
    validationError: ValidationError,
) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        dictFieldMessage: dict[str, list[str]] = {}
        hasDuplicateName = False
        for fieldName, listFieldError in validationError.error_dict.items():
            for fieldError in listFieldError:
                isDuplicateName = fieldError.code == "duplicate_department_name"
                hasDuplicateName = hasDuplicateName or isDuplicateName
                responseFieldName = (
                    "name"
                    if isDuplicateName
                    else "parent_id"
                    if fieldName == "parent"
                    else fieldName
                )
                dictFieldMessage.setdefault(responseFieldName, []).extend(
                    fieldError.messages
                )
        return JsonResponse(
            {
                "error": {
                    "code": (
                        "duplicate_department_name"
                        if hasDuplicateName
                        else "invalid_department"
                    ),
                    "message": "Some department fields are invalid.",
                    "fields": dictFieldMessage,
                }
            },
            status=409 if hasDuplicateName else 400,
        )

    errorCode = validationError.error_list[0].code or "invalid_department"
    return build_error_response(
        errorCode,
        " ".join(validationError.messages),
        statusCode=409 if errorCode == "department_count_limit" else 400,
    )


@never_cache
@require_http_methods(["GET", "POST"])
def list_or_create_departments(request: HttpRequest) -> JsonResponse:
    """Read the department tree or create a department with administrator permission."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        if request.method == "POST":
            departmentRequest = parse_json_request(
                request,
                DepartmentCreationRequest,
                maxBodyBytes=_INT_MAX_DEPARTMENT_BODY_BYTES,
            )
            if isinstance(departmentRequest, JsonResponse):
                return departmentRequest
            department = create_department(
                actorId=user.id,
                organizationId=membership.organization_id,
                channel=AccessChannel.SESSION,
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
        return JsonResponse({
            "departments": [
                _build_department_payload(departmentInfo)
                for departmentInfo in listDepartmentInfo
            ]
        })
    except ValidationError as e:
        return _build_department_validation_response(e)
    except PermissionDenied:
        return build_error_response(
            "department_access_required",
            "Department administration is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_department(
    request: HttpRequest, departmentId: uuid.UUID
) -> JsonResponse:
    """Read or edit one current department without changing its stable identity."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        if request.method == "POST":
            departmentRequest = parse_json_request(
                request,
                DepartmentUpdateRequest,
                maxBodyBytes=_INT_MAX_DEPARTMENT_BODY_BYTES,
            )
            if isinstance(departmentRequest, JsonResponse):
                return departmentRequest
            department = update_department(
                actorId=user.id,
                organizationId=membership.organization_id,
                channel=AccessChannel.SESSION,
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
        return JsonResponse({
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
        })
    except ValidationError as e:
        return _build_department_validation_response(e)
    except Department.DoesNotExist:
        return build_error_response(
            "department_not_found", "Department not found or unavailable.", statusCode=404
        )
    except PermissionDenied:
        return build_error_response(
            "department_access_required",
            "Department administration is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )


def _build_department_deletion_payload(
    deletionInfo: DepartmentDeletionInfo,
) -> dict[str, object]:
    return {
        "department": {
            "id": deletionInfo.departmentId,
            "name": deletionInfo.departmentName,
        },
        "can_delete": deletionInfo.canDelete,
        "blockers": [
            {"code": blocker.code, "count": blocker.count}
            for blocker in deletionInfo.blockers
        ],
    }


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_delete_department(
    request: HttpRequest, departmentId: uuid.UUID
) -> JsonResponse:
    """Preview current deletion blockers or submit a fresh deletion attempt."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        if request.method == "POST":
            deletionRequest = parse_json_request(request, DepartmentDeletionRequest)
            if isinstance(deletionRequest, JsonResponse):
                return deletionRequest
            department = delete_department(
                actorId=user.id,
                organizationId=membership.organization_id,
                channel=AccessChannel.SESSION,
                departmentId=departmentId,
            )
            return JsonResponse({
                "department": {
                    "id": department.id,
                    "name": department.name,
                    "deleted_at": department.deleted_at,
                }
            })

        deletionInfo = get_department_deletion_info(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            departmentId=departmentId,
        )
        return JsonResponse(_build_department_deletion_payload(deletionInfo))
    except DepartmentDeletionBlockedError as e:
        return JsonResponse(
            {
                **_build_department_deletion_payload(e.deletionInfo),
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
    except Department.DoesNotExist:
        return build_error_response(
            "department_not_found", "Department not found or unavailable.", statusCode=404
        )
    except PermissionDenied:
        return build_error_response(
            "department_access_required",
            "Department administration is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )
