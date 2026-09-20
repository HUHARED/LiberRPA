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
from pydantic import BaseModel, ConfigDict

from .rate_limits import reserve_registration_email_request
from .registration import request_registration_email

_MAX_REGISTRATION_BODY_BYTES = 4096


class RegistrationEmailRequest(BaseModel):
    """Validate the HTTP envelope; the email service owns address validation."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )
    email: str


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON fields are not allowed.")
        result[name] = value
    return result


def _error_response(code: str, message: str, *, statusCode: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=statusCode)


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
        payload = RegistrationEmailRequest.model_validate(
            json.loads(body.decode("utf-8"), object_pairs_hook=_unique_json_object)
        )
    except (ValueError, RecursionError):
        return _error_response(
            "invalid_request",
            "Send a JSON object containing only an email string.",
            statusCode=400,
        )

    try:
        # Uvicorn must disable proxy headers until a trusted proxy is configured.
        retryAfter = reserve_registration_email_request(
            request.META.get("REMOTE_ADDR", "")
        )
        if retryAfter:
            response = _error_response(
                "rate_limited", "Too many requests. Try again later.", statusCode=429
            )
            response["Retry-After"] = str(retryAfter)
            return response
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
