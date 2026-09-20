# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST
from pydantic import BaseModel, ConfigDict, SecretStr

from .rate_limits import (
    reserve_registration_email_request,
    reserve_registration_token_request,
)
from .registration import (
    complete_organization_registration,
    get_registration_email,
    request_registration_email,
)

_MAX_REGISTRATION_BODY_BYTES = 4096


class _RegistrationRequest(BaseModel):
    """Validate HTTP field types; registration services own business validation."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


class RegistrationEmailRequest(_RegistrationRequest):
    email: str


class RegistrationTokenRequest(_RegistrationRequest):
    token: SecretStr


class RegistrationCompletionRequest(RegistrationTokenRequest):
    password: SecretStr
    organization_name: str
    username: str = ""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON fields are not allowed.")
        # Reject escaped lone surrogates before strings reach hashing or the database.
        name.encode("utf-8")
        if isinstance(value, str):
            value.encode("utf-8")
        result[name] = value
    return result


def _error_response(code: str, message: str, *, statusCode: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=statusCode)


@sensitive_variables()
def _read_json_request[Payload: BaseModel](
    request: HttpRequest, schema: type[Payload]
) -> Payload | JsonResponse:
    if request.content_type != "application/json":
        return _error_response(
            "unsupported_media_type", "Send application/json.", statusCode=415
        )

    body = request.read(_MAX_REGISTRATION_BODY_BYTES + 1)
    if len(body) > _MAX_REGISTRATION_BODY_BYTES:
        return _error_response(
            "request_too_large", "The request body is too large.", statusCode=413
        )
    try:
        return schema.model_validate(
            json.loads(body.decode("utf-8"), object_pairs_hook=_unique_json_object)
        )
    except (ValueError, RecursionError):
        return _error_response(
            "invalid_request",
            "Send a JSON object with the required string fields and no unknown fields.",
            statusCode=400,
        )


def _rate_limited_response(retryAfter: int) -> JsonResponse:
    response = _error_response(
        "rate_limited", "Too many requests. Try again later.", statusCode=429
    )
    response["Retry-After"] = str(retryAfter)
    return response


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
    payload = _read_json_request(request, RegistrationEmailRequest)
    if isinstance(payload, JsonResponse):
        return payload
    try:
        # Uvicorn must disable proxy headers until a trusted proxy is configured.
        retryAfter = reserve_registration_email_request(
            request.META.get("REMOTE_ADDR", "")
        )
        if retryAfter:
            return _rate_limited_response(retryAfter)
        request_registration_email(payload.email)
    except DjangoValidationError:
        return _error_response(
            "invalid_email", "Enter a valid email address.", statusCode=400
        )
    except PermissionDenied:
        return _error_response(
            "organization_creation_disabled",
            "Organization creation is currently unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return _error_response(
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
    payload = _read_json_request(request, RegistrationTokenRequest)
    if isinstance(payload, JsonResponse):
        return payload
    try:
        token = payload.token.get_secret_value()
        retryAfter = reserve_registration_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfter:
            return _rate_limited_response(retryAfter)
        return JsonResponse({"email": get_registration_email(token)})
    except DjangoValidationError as e:
        return _registration_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return _error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )


@never_cache
@require_POST
@sensitive_variables()
def complete_registration(request: HttpRequest) -> JsonResponse:
    """Atomically create the account and organization using the token's fixed email."""
    payload = _read_json_request(request, RegistrationCompletionRequest)
    if isinstance(payload, JsonResponse):
        return payload
    try:
        token = payload.token.get_secret_value()
        retryAfter = reserve_registration_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfter:
            return _rate_limited_response(retryAfter)
        complete_organization_registration(
            token=token,
            password=payload.password.get_secret_value(),
            organizationName=payload.organization_name,
            username=payload.username,
        )
    except DjangoValidationError as e:
        return _registration_validation_response(e)
    except PermissionDenied:
        return _error_response(
            "organization_creation_disabled",
            "Organization creation is currently unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return _error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )
    return JsonResponse(
        {"message": "Organization created. Sign in to continue."}, status=201
    )
