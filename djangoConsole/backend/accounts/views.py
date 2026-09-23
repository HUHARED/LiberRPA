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
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
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


def _build_registration_validation_response(
    validationError: DjangoValidationError,
) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        # The organization model calls this field "name"; the HTTP form is explicit.
        dictFieldError = {
            "organization_name" if fieldName == "name" else fieldName: listErrorMessage
            for fieldName, listErrorMessage in validationError.message_dict.items()
        }
        return build_error_response(
            "invalid_registration",
            "Some registration fields are invalid.",
            statusCode=400,
            fields=dictFieldError,
        )

    errorCode = validationError.error_list[0].code or "invalid_registration"
    passwordFields: dict[str, list[str]] | None = None
    if all(
        fieldError.code and fieldError.code.startswith("password_")
        for fieldError in validationError.error_list
    ):
        passwordFields = {"password": validationError.messages}
    statusCode = 409 if errorCode == "email_already_registered" else 400
    return build_error_response(
        errorCode,
        " ".join(validationError.messages),
        statusCode=statusCode,
        fields=passwordFields,
    )


@never_cache
@require_GET
def get_csrf_token(request: HttpRequest) -> JsonResponse:
    """Issue a masked token and its matching cookie for subsequent browser requests."""
    return JsonResponse({"csrf_token": get_token(request)})


@never_cache
@require_POST
@sensitive_variables()
def queue_registration_email(request: HttpRequest) -> JsonResponse:
    """Accept a CSRF-protected request without exposing account or delivery state."""
    registrationRequest = parse_json_request(request, RegistrationEmailRequest)
    if isinstance(registrationRequest, JsonResponse):
        return registrationRequest
    try:
        # Uvicorn must disable proxy headers until a trusted proxy is configured.
        retryAfterSeconds = reserve_registration_email_request(
            request.META.get("REMOTE_ADDR", "")
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)
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
        token = registrationRequest.token.get_secret_value()
        retryAfterSeconds = reserve_registration_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)
        return JsonResponse({"email": get_registration_email(token)})
    except DjangoValidationError as e:
        return _build_registration_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_POST
@sensitive_variables()
def complete_registration(request: HttpRequest) -> JsonResponse:
    """Atomically create the account and organization using the token's fixed email."""
    registrationRequest = parse_json_request(request, RegistrationCompletionRequest)
    if isinstance(registrationRequest, JsonResponse):
        return registrationRequest
    try:
        token = registrationRequest.token.get_secret_value()
        retryAfterSeconds = reserve_registration_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)
        complete_organization_registration(
            token=token,
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
