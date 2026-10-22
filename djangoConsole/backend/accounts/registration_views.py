# FileName: registration_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
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

from .models import User
from .rate_limits import (
    apply_registration_email_rate_limit,
    apply_registration_token_rate_limit,
)
from .registration import (
    complete_organization_registration,
    get_registration_email,
    request_registration_email,
)


class RegistrationEmailRequest(JsonRequest):
    email: str


class RegistrationTokenRequest(JsonRequest):
    token: SecretStr


class RegistrationCompletionRequest(RegistrationTokenRequest):
    password: SecretStr
    organization_name: str
    username: str = ""


def _build_registration_validation_response(
    validationError: DjangoValidationError,
) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        # The organization model calls this field "name"; the HTTP form is explicit.
        dictFieldError = {
            "organization_name"
            if strFieldName == "name"
            else strFieldName: listErrorMessage
            for strFieldName, listErrorMessage in validationError.message_dict.items()
        }
        return build_error_response(
            "invalid_registration",
            "Some registration fields are invalid.",
            statusCode=400,
            fields=dictFieldError,
        )

    strErrorCode = validationError.error_list[0].code or "invalid_registration"
    dictPasswordField: dict[str, list[str]] | None = None
    if all(
        fieldError.code and fieldError.code.startswith("password_")
        for fieldError in validationError.error_list
    ):
        dictPasswordField = {"password": validationError.messages}
    intStatusCode = 409 if strErrorCode == "email_already_registered" else 400
    return build_error_response(
        strErrorCode,
        " ".join(validationError.messages),
        statusCode=intStatusCode,
        fields=dictPasswordField,
    )


@never_cache
@require_POST
@sensitive_variables()
def queue_registration_email(request: HttpRequest) -> JsonResponse:
    """Accept a CSRF-protected request without exposing account or delivery state."""
    if request.user.is_authenticated and cast(User, request.user).is_platform_admin:
        return build_error_response(
            "business_registration_unavailable",
            "Platform accounts cannot register business accounts.",
            statusCode=403,
        )
    registrationRequest = parse_json_request(request, RegistrationEmailRequest)
    if isinstance(registrationRequest, JsonResponse):
        return registrationRequest
    try:
        # Uvicorn must disable proxy headers until a trusted proxy is configured.
        intRetryAfterSeconds = apply_registration_email_rate_limit(
            request.META.get("REMOTE_ADDR", "")
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        request_registration_email(registrationRequest.email)
    except DjangoValidationError:
        return build_error_response(
            "invalid_email", "Enter a valid email address.", statusCode=400
        )
    except PermissionDenied:
        return build_error_response(
            "organization_creation_disabled",
            "Organization creation is currently unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()

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
    registrationRequest = parse_json_request(request, RegistrationTokenRequest)
    if isinstance(registrationRequest, JsonResponse):
        return registrationRequest
    try:
        strToken = registrationRequest.token.get_secret_value()
        intRetryAfterSeconds = apply_registration_token_rate_limit(
            request.META.get("REMOTE_ADDR", ""), token=strToken
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        return JsonResponse({"email": get_registration_email(strToken)})
    except DjangoValidationError as e:
        return _build_registration_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_POST
@sensitive_variables()
def complete_registration(request: HttpRequest) -> JsonResponse:
    """Atomically create the account and organization using the token's fixed email."""
    if request.user.is_authenticated and cast(User, request.user).is_platform_admin:
        return build_error_response(
            "business_registration_unavailable",
            "Platform accounts cannot register business accounts.",
            statusCode=403,
        )
    registrationRequest = parse_json_request(request, RegistrationCompletionRequest)
    if isinstance(registrationRequest, JsonResponse):
        return registrationRequest
    try:
        strToken = registrationRequest.token.get_secret_value()
        intRetryAfterSeconds = apply_registration_token_rate_limit(
            request.META.get("REMOTE_ADDR", ""), token=strToken
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        complete_organization_registration(
            token=strToken,
            password=registrationRequest.password.get_secret_value(),
            organizationName=registrationRequest.organization_name,
            username=registrationRequest.username,
        )
    except DjangoValidationError as e:
        return _build_registration_validation_response(e)
    except PermissionDenied:
        return build_error_response(
            "organization_creation_disabled",
            "Organization creation is currently unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
    return JsonResponse(
        {"message": "Organization created. Sign in to continue."}, status=201
    )
