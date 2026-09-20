# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST
from pydantic import SecretStr

from .http import (
    AccountRequest,
    error_response,
    rate_limited_response,
    read_json_request,
)
from .rate_limits import (
    reserve_registration_email_request,
    reserve_registration_token_request,
)
from .registration import (
    complete_organization_registration,
    get_registration_email,
    request_registration_email,
)


class RegistrationEmailRequest(AccountRequest):
    email: str


class RegistrationTokenRequest(AccountRequest):
    token: SecretStr


class RegistrationCompletionRequest(RegistrationTokenRequest):
    password: SecretStr
    organization_name: str
    username: str = ""


def _registration_validation_response(error: DjangoValidationError) -> JsonResponse:
    if hasattr(error, "error_dict"):
        # The organization model calls this field "name"; the HTTP form is explicit.
        fields = {
            "organization_name" if name == "name" else name: messages
            for name, messages in error.message_dict.items()
        }
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_registration",
                    "message": "Some registration fields are invalid.",
                    "fields": fields,
                }
            },
            status=400,
        )

    code = error.error_list[0].code or "invalid_registration"
    details: dict[str, object] = {"code": code, "message": " ".join(error.messages)}
    if all(item.code and item.code.startswith("password_") for item in error.error_list):
        details["fields"] = {"password": error.messages}
    statusCode = 409 if code == "email_already_registered" else 400
    return JsonResponse({"error": details}, status=statusCode)


@never_cache
@require_GET
def get_csrf_token(request: HttpRequest) -> JsonResponse:
    """Issue a masked token and its matching cookie for subsequent browser requests."""
    return JsonResponse({"csrf_token": get_token(request)})


@never_cache
@require_POST
@sensitive_variables()
def send_registration_email(request: HttpRequest) -> JsonResponse:
    """Accept a CSRF-protected request without exposing account or delivery state."""
    payload = read_json_request(request, RegistrationEmailRequest)
    if isinstance(payload, JsonResponse):
        return payload
    try:
        # Uvicorn must disable proxy headers until a trusted proxy is configured.
        retryAfter = reserve_registration_email_request(
            request.META.get("REMOTE_ADDR", "")
        )
        if retryAfter:
            return rate_limited_response(retryAfter)
        request_registration_email(payload.email)
    except DjangoValidationError:
        return error_response(
            "invalid_email", "Enter a valid email address.", statusCode=400
        )
    except PermissionDenied:
        return error_response(
            "organization_creation_disabled",
            "Organization creation is currently unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )

    # Existing accounts, recipient cooldowns, and newly queued mail share this response.
    return JsonResponse(
        {"message": "If this address is eligible, a verification email will be sent."},
        status=202,
    )


@never_cache
@require_POST
@sensitive_variables()
def check_registration_link(request: HttpRequest) -> JsonResponse:
    """Return the verified address without consuming the token or creating records."""
    payload = read_json_request(request, RegistrationTokenRequest)
    if isinstance(payload, JsonResponse):
        return payload
    try:
        token = payload.token.get_secret_value()
        retryAfter = reserve_registration_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfter:
            return rate_limited_response(retryAfter)
        return JsonResponse({"email": get_registration_email(token)})
    except DjangoValidationError as e:
        return _registration_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )


@never_cache
@require_POST
@sensitive_variables()
def complete_registration(request: HttpRequest) -> JsonResponse:
    """Atomically create the account and organization using the token's fixed email."""
    payload = read_json_request(request, RegistrationCompletionRequest)
    if isinstance(payload, JsonResponse):
        return payload
    try:
        token = payload.token.get_secret_value()
        retryAfter = reserve_registration_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfter:
            return rate_limited_response(retryAfter)
        complete_organization_registration(
            token=token,
            password=payload.password.get_secret_value(),
            organizationName=payload.organization_name,
            username=payload.username,
        )
    except DjangoValidationError as e:
        return _registration_validation_response(e)
    except PermissionDenied:
        return error_response(
            "organization_creation_disabled",
            "Organization creation is currently unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )
    return JsonResponse(
        {"message": "Organization created. Sign in to continue."}, status=201
    )
