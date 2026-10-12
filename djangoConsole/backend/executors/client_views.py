# FileName: client_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import Annotated, cast

from django.contrib.auth import authenticate
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST
from pydantic import Field, SecretStr

from accounts.models import User, UserManager
from accounts.rate_limits import apply_executor_client_rate_limit, apply_login_rate_limit
from console_project.contracts import JsonRequest
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)
from organizations.access import get_department_access_info
from organizations.permissions import OrganizationAccessContext

from .client_sessions import (
    InvalidExecutorSessionError,
    ExecutorClientAction,
    begin_executor_login,
    get_executor_session_identity,
    open_executor_client_request,
)
from .models import Executor, ExecutorSession

_HANDLED_CLIENT_ERRORS = (
    InvalidExecutorSessionError,
    PermissionDenied,
    ValidationError,
    Executor.DoesNotExist,
    InvalidPage,
    ImproperlyConfigured,
    DatabaseError,
)
_DICT_CLIENT_METHOD = {
    ExecutorClientAction.CHOICES: "GET",
    ExecutorClientAction.ASSOCIATE: "POST",
    ExecutorClientAction.SESSION: "GET",
    ExecutorClientAction.LOGOUT: "POST",
}


class ExecutorLoginRequest(JsonRequest):
    email: str
    password: SecretStr
    computer_name: str
    client_version: str


class ExecutorAssociationRequest(JsonRequest):
    executor_id: Annotated[uuid.UUID, Field(strict=False)]


class ExecutorContactRequest(JsonRequest):
    """The verified session identifies the account and Executor; no overrides are accepted."""


def _build_client_error_response(e: Exception) -> JsonResponse:
    match e:
        case InvalidExecutorSessionError():
            response = build_error_response(
                "executor_authentication_required",
                "A valid Executor session is required.",
                statusCode=401,
            )
            response["WWW-Authenticate"] = 'Bearer realm="LiberRPA Executor"'
            return response
        case PermissionDenied():
            return build_error_response(
                "organization_access_required",
                "Organization business access is unavailable.",
                statusCode=403,
            )
        case Executor.DoesNotExist():
            return build_error_response(
                "executor_not_found", "The Executor is unavailable.", statusCode=404
            )
        case InvalidPage():
            return build_error_response(
                "invalid_page", "The requested page is unavailable.", statusCode=400
            )
        case ValidationError():
            strErrorCode = getattr(e, "code", None)
            if strErrorCode in (
                "executor_already_associated",
                "executor_selection_required",
            ):
                return build_error_response(strErrorCode, e.messages[0], statusCode=409)
            return build_error_response(
                "invalid_executor_client",
                "Some Executor client fields are invalid.",
                statusCode=400,
                fields=e.message_dict
                if hasattr(e, "error_dict")
                else {"__all__": e.messages},
            )
        case _:
            return build_service_unavailable_response()


def build_client_session_payload(
    session: ExecutorSession, access: OrganizationAccessContext
) -> dict[str, object]:
    user = cast(User, session.user)
    tupleDepartmentAccessInfo = get_department_access_info(access)
    executor = cast(Executor | None, session.executor)
    return {
        "session": {
            "id": session.id,
            "selection_required": session.executor_id is None,
            "expires_at": session.expires_at,
        },
        "user": {"id": user.id, "email": user.email, "username": user.username},
        "organization": {"id": access.organization.id, "name": access.organization.name},
        "is_org_admin": access.isOrgAdmin,
        "account_departments": [
            {
                "id": department.id,
                "name": department.name,
                "path": department.path,
                "role": department.role,
            }
            for department in tupleDepartmentAccessInfo
        ],
        "executor": None
        if executor is None
        else {
            "id": executor.id,
            "name": executor.name,
            "department_id": executor.department_id,
            "dispatch_enabled": executor.dispatch_enabled,
        },
        "computer_name": session.computer_name,
        "client_version": session.client_version,
        "last_seen_at": session.last_seen_at,
        "heartbeat_interval_seconds": 15,
    }


# Native endpoints authenticate explicit credentials only; browser cookies never authorize them.
@csrf_exempt
@never_cache
@require_POST
@sensitive_variables()
def sign_in_executor(request: HttpRequest) -> JsonResponse:
    loginRequest = parse_json_request(request, ExecutorLoginRequest)
    if isinstance(loginRequest, JsonResponse):
        return loginRequest
    try:
        strNormalizedEmail = UserManager.normalize_email(loginRequest.email)
        intRetryAfterSeconds = apply_login_rate_limit(
            request.META.get("REMOTE_ADDR", ""), normalizedEmail=strNormalizedEmail
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        user = cast(
            User | None,
            authenticate(
                request,
                email=strNormalizedEmail,
                password=loginRequest.password.get_secret_value(),
            ),
        )
        if user is None:
            return build_error_response(
                "invalid_credentials",
                "The email or password is incorrect.",
                statusCode=401,
            )
        result = begin_executor_login(
            userId=user.id,
            verifiedAuthHash=user.get_session_auth_hash(),
            computerName=loginRequest.computer_name,
            clientVersion=loginRequest.client_version,
        )
        return JsonResponse({
            **build_client_session_payload(result.session, result.access),
            "token": result.token,
        })
    except _HANDLED_CLIENT_ERRORS as e:
        return _build_client_error_response(e)


@csrf_exempt
@never_cache
@sensitive_variables()
def process_executor_client_request(
    request: HttpRequest, action: ExecutorClientAction
) -> JsonResponse:
    """Adapt a server-selected route action; request data cannot choose another operation."""
    strAllowedMethod = _DICT_CLIENT_METHOD[action]
    if request.method != strAllowedMethod:
        response = build_error_response(
            "method_not_allowed",
            f"Use {strAllowedMethod} for this operation.",
            statusCode=405,
        )
        response["Allow"] = strAllowedMethod
        return response
    try:
        if action != ExecutorClientAction.LOGOUT:
            intRetryAfterSeconds = apply_executor_client_rate_limit(
                request.META.get("REMOTE_ADDR", "")
            )
            if intRetryAfterSeconds:
                return build_rate_limited_response(intRetryAfterSeconds)
        intPageNumber = 1
        if request.GET:
            listPageValue = request.GET.getlist("page")
            if (
                action != ExecutorClientAction.CHOICES
                or set(request.GET) != {"page"}
                or len(listPageValue) != 1
                or not listPageValue[0].isascii()
                or not listPageValue[0].isdecimal()
                or len(listPageValue[0]) > 9
                or int(listPageValue[0]) < 1
            ):
                return build_error_response(
                    "invalid_request",
                    "Only choices accepts one positive page number.",
                    statusCode=400,
                )
            intPageNumber = int(listPageValue[0])
        executorId = None
        if action == ExecutorClientAction.ASSOCIATE:
            associationRequest = parse_json_request(request, ExecutorAssociationRequest)
            if isinstance(associationRequest, JsonResponse):
                return associationRequest
            executorId = associationRequest.executor_id
        elif request.method == "POST":
            contactRequest = parse_json_request(request, ExecutorContactRequest)
            if isinstance(contactRequest, JsonResponse):
                return contactRequest
        with open_executor_client_request(
            identity=get_executor_session_identity(
                request.headers.get("Authorization", "")
            ),
            action=action,
            executorId=executorId,
            pageNumber=intPageNumber,
        ) as result:
            if result is None:
                return JsonResponse({"message": "Signed out."})
            dictSessionPayload = build_client_session_payload(
                result.session, result.access
            )
            if result.choices is not None:
                page = result.choices
                dictSessionPayload.update({
                    "executors": [
                        {
                            "id": entry.executor.id,
                            "name": entry.executor.name,
                            "department": {
                                "id": entry.executor.department_id,
                                "name": entry.executor.department.name,
                                "path": entry.departmentPath,
                            },
                            "dispatch_enabled": entry.executor.dispatch_enabled,
                        }
                        for entry in page.executors
                    ],
                    "page": page.page,
                    "page_size": page.pageSize,
                    "total_count": page.totalCount,
                    "total_pages": page.totalPages,
                })
            return JsonResponse(dictSessionPayload)
    except _HANDLED_CLIENT_ERRORS as e:
        return _build_client_error_response(e)
