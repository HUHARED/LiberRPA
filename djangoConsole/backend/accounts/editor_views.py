# FileName: editor_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.contrib.auth import authenticate
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST
from pydantic import SecretStr

from console_project.contracts import JsonRequest
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)
from organizations.access import get_department_access_info

from .models import User, UserManager
from .rate_limits import apply_login_rate_limit, apply_editor_client_rate_limit
from .editor_sessions import (
    InvalidEditorSessionError,
    EditorClientAction,
    EditorClientResult,
    begin_editor_login,
    handle_editor_client_request,
)

_HANDLED_CLIENT_ERRORS = (
    InvalidEditorSessionError,
    PermissionDenied,
    ValidationError,
    ImproperlyConfigured,
    DatabaseError,
)
_DICT_CLIENT_METHOD = {
    EditorClientAction.SESSION: "GET",
    EditorClientAction.LOGOUT: "POST",
}


class EditorLoginRequest(JsonRequest):
    email: str
    password: SecretStr
    computer: str
    version: str


class EditorLogoutRequest(JsonRequest):
    """Identity always comes from the explicit Editor credential."""


def _build_client_error_response(e: Exception) -> JsonResponse:
    match e:
        case InvalidEditorSessionError():
            response = build_error_response(
                "editor_authentication_required",
                "A valid Editor session is required.",
                statusCode=401,
            )
            response["WWW-Authenticate"] = 'Bearer realm="LiberRPA Editor"'
            return response
        case PermissionDenied():
            return build_error_response(
                "organization_access_required",
                "Organization business access is unavailable.",
                statusCode=403,
            )
        case ValidationError():
            return build_error_response(
                "invalid_editor_client",
                "Some Editor client fields are invalid.",
                statusCode=400,
                fields=e.message_dict
                if hasattr(e, "error_dict")
                else {"__all__": e.messages},
            )
        case _:
            return build_service_unavailable_response()


def _build_client_session_payload(result: EditorClientResult) -> dict[str, object]:
    session = result.session
    access = result.access
    user = access.actor
    return {
        "session": {"id": session.id, "expires_at": session.expires_at},
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
            for department in get_department_access_info(access)
        ],
        "computer": session.computer,
        "version": session.client_version,
        "last_seen_at": session.last_seen_at,
    }


# Native endpoints never accept browser cookies in place of explicit credentials.
@csrf_exempt
@never_cache
@require_POST
@sensitive_variables()
def sign_in_editor(request: HttpRequest) -> JsonResponse:
    loginRequest = parse_json_request(request, EditorLoginRequest)
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
        result = begin_editor_login(
            userId=user.id,
            verifiedAuthHash=user.get_session_auth_hash(),
            computer=loginRequest.computer,
            clientVersion=loginRequest.version,
        )
        return JsonResponse({
            **_build_client_session_payload(result),
            "token": result.token,
        })
    except _HANDLED_CLIENT_ERRORS as e:
        return _build_client_error_response(e)


@csrf_exempt
@never_cache
@sensitive_variables()
def process_editor_client_request(
    request: HttpRequest, action: EditorClientAction
) -> JsonResponse:
    strAllowedMethod = _DICT_CLIENT_METHOD[action]
    if request.method != strAllowedMethod:
        response = build_error_response(
            "method_not_allowed",
            f"Use {strAllowedMethod} for this operation.",
            statusCode=405,
        )
        response["Allow"] = strAllowedMethod
        return response
    if request.GET:
        return build_error_response(
            "invalid_request", "Query parameters are not accepted.", statusCode=400
        )
    try:
        if action != EditorClientAction.LOGOUT:
            intRetryAfterSeconds = apply_editor_client_rate_limit(
                request.META.get("REMOTE_ADDR", "")
            )
            if intRetryAfterSeconds:
                return build_rate_limited_response(intRetryAfterSeconds)
        if request.method == "POST":
            logoutRequest = parse_json_request(request, EditorLogoutRequest)
            if isinstance(logoutRequest, JsonResponse):
                return logoutRequest
        result = handle_editor_client_request(
            authorizationHeader=request.headers.get("Authorization", ""), action=action
        )
        if result is None:
            return JsonResponse({"message": "Signed out."})
        return JsonResponse(_build_client_session_payload(result))
    except _HANDLED_CLIENT_ERRORS as e:
        return _build_client_error_response(e)
