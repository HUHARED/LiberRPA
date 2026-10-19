# FileName: public_api_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET

from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
)
from organizations.access import get_department_access_info
from organizations.contracts import DepartmentRole
from organizations.rate_limits import check_request_budget

from .api_key_authentication import InvalidApiKeyError, authenticate_api_key
from .rate_limits import apply_api_key_authentication_rate_limit


@never_cache
@require_GET
@sensitive_variables()
def get_api_key_access(request: HttpRequest) -> JsonResponse:
    """Return current Operator access using only the Authorization header, without a session."""
    try:
        intRetryAfterSeconds = apply_api_key_authentication_rate_limit(
            request.META.get("REMOTE_ADDR", "")
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        if request.GET:
            return build_error_response(
                "invalid_request",
                "This endpoint does not accept query parameters.",
                statusCode=400,
            )

        authentication = authenticate_api_key(request.headers.get("Authorization", ""))
        access = authentication.access
        check_request_budget(request, access.organization.pk)
        tupleDepartmentAccessInfo = get_department_access_info(access)
        return JsonResponse({
            "api_key": {
                "id": authentication.apiKeyId,
                "expires_at": authentication.expiresAt,
            },
            "user_id": access.actorId,
            "organization": {
                "id": access.organization.pk,
                "name": access.organization.name,
            },
            "role": DepartmentRole.OPERATOR,
            "departments": [
                {
                    "id": department.id,
                    "name": department.name,
                    "path": department.path,
                    "role": department.role,
                }
                for department in tupleDepartmentAccessInfo
            ],
        })
    except InvalidApiKeyError:
        response = build_error_response(
            "api_key_authentication_required",
            "A valid API key is required.",
            statusCode=401,
        )
        strChallenge = 'Bearer realm="LiberRPA Console"'
        if request.headers.get("Authorization"):
            strChallenge += ', error="invalid_token"'
        response["WWW-Authenticate"] = strChallenge
        return response
    except PermissionDenied:
        return build_error_response(
            "organization_access_required",
            "Organization business access is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
