# FileName: api_key_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import timedelta
from typing import cast

from django.conf import settings
from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from console_project.config import LimitsConfig
from organizations.models import Membership
from organizations.permissions import AccessChannel

from .api_keys import (
    create_api_key,
    get_api_key_list,
    get_api_key_status,
    revoke_api_key,
    update_api_key_notes,
)
from .http import (
    AccountRequest,
    build_error_response,
    build_rate_limited_response,
    parse_json_request,
)
from .models import ApiKey, ApiKeyStatus, User
from .rate_limits import reserve_api_key_creation_request
from .session_revocation import SessionInvalidatedError

_INT_MAX_API_KEY_BODY_BYTES = 16 * 1024


class ApiKeyCreateRequest(AccountRequest):
    name: str
    expires_at: str
    notes: str = ""


class ApiKeyNotesRequest(AccountRequest):
    notes: str


def _build_api_key_payload(apiKey: ApiKey) -> dict[str, object]:
    # Use an explicit allowlist; the digest and plaintext never belong in metadata responses.
    return {
        "id": apiKey.id,
        "name": apiKey.name,
        "status": get_api_key_status(apiKey, currentTime=timezone.now()),
        "expires_at": apiKey.expires_at,
        "last_used_at": apiKey.last_used_at,
        "notes": apiKey.notes,
        "created_at": apiKey.created_at,
        "revoked_at": apiKey.revoked_at,
    }


def _build_api_key_error_response(e: Exception) -> JsonResponse:
    if isinstance(e, SessionInvalidatedError):
        return build_error_response(
            "authentication_required", "Sign in again to continue.", statusCode=401
        )
    if isinstance(e, PermissionDenied):
        return build_error_response(
            "api_key_access_required",
            "API key management is unavailable.",
            statusCode=403,
        )
    if isinstance(e, (ApiKey.DoesNotExist, Membership.DoesNotExist)):
        return build_error_response(
            "api_key_not_found", "The member or API key is unavailable.", statusCode=404
        )
    if isinstance(e, ValidationError):
        errorCode = getattr(e, "code", None)
        if errorCode in ("api_key_limit", "api_key_not_active"):
            return build_error_response(errorCode, e.messages[0], statusCode=409)
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_api_key",
                    "message": "Some API key fields are invalid.",
                    "fields": e.message_dict
                    if hasattr(e, "error_dict")
                    else {"__all__": e.messages},
                }
            },
            status=400,
        )
    return build_error_response(
        "service_unavailable", "The service is temporarily unavailable.", statusCode=503
    )


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_variables()
def list_or_create_api_keys(
    request: HttpRequest, userId: uuid.UUID | None = None
) -> JsonResponse:
    """Manage the owner's keys or read a member's metadata through an administrator session."""
    if userId is not None and request.method != "GET":
        response = build_error_response(
            "method_not_allowed",
            "Only GET is allowed for member API keys.",
            statusCode=405,
        )
        response["Allow"] = "GET"
        return response
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        if request.method == "POST":
            keyRequest = parse_json_request(
                request, ApiKeyCreateRequest, maxBodyBytes=_INT_MAX_API_KEY_BODY_BYTES
            )
            if isinstance(keyRequest, JsonResponse):
                return keyRequest
            retryAfterSeconds = reserve_api_key_creation_request(
                request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
            )
            if retryAfterSeconds:
                return build_rate_limited_response(retryAfterSeconds)
            try:
                expiresAt = parse_datetime(keyRequest.expires_at)
            except ValueError:
                expiresAt = None
            if expiresAt is None:
                raise ValidationError({
                    "expires_at": "Enter an ISO 8601 time with a UTC offset."
                })
            result = create_api_key(
                actorId=user.id,
                channel=AccessChannel.SESSION,
                name=keyRequest.name,
                expiresAt=expiresAt,
                notes=keyRequest.notes,
                sessionAuthHash=request.session.get(HASH_SESSION_KEY, ""),
                sessionExpiresAt=request.session.get_expiry_date(),
            )
            return JsonResponse(
                {
                    "api_key": _build_api_key_payload(result.apiKey),
                    "secret": result.secret,
                },
                status=201,
            )

        try:
            statuses = tuple(
                ApiKeyStatus(value) for value in request.GET.getlist("status")
            )
            if set(request.GET) - {"status"}:
                raise ValueError
        except ValueError:
            raise ValidationError({
                "status": "Use active, expired, or revoked status values."
            }) from None
        apiKeys = get_api_key_list(
            actorId=user.id,
            channel=AccessChannel.SESSION,
            userId=user.id if userId is None else userId,
            statuses=statuses,
            asAdministrator=userId is not None,
        )
        limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
        return JsonResponse({
            "api_keys": [_build_api_key_payload(apiKey) for apiKey in apiKeys],
            "default_expires_at": timezone.now() + timedelta(days=365),
            "limits": {
                "active_keys": limits.maxActiveApiKeysPerAccount,
                "inactive_retention_days": limits.inactiveApiKeyRetentionDays,
                "inactive_records": limits.maxInactiveApiKeysPerAccount,
            },
        })
    except (
        ValidationError,
        PermissionDenied,
        ApiKey.DoesNotExist,
        Membership.DoesNotExist,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_api_key_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def edit_api_key_notes(request: HttpRequest, apiKeyId: uuid.UUID) -> JsonResponse:
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        keyRequest = parse_json_request(
            request, ApiKeyNotesRequest, maxBodyBytes=_INT_MAX_API_KEY_BODY_BYTES
        )
        if isinstance(keyRequest, JsonResponse):
            return keyRequest
        apiKey = update_api_key_notes(
            actorId=cast(User, request.user).id,
            channel=AccessChannel.SESSION,
            apiKeyId=apiKeyId,
            notes=keyRequest.notes,
            sessionAuthHash=request.session.get(HASH_SESSION_KEY, ""),
            sessionExpiresAt=request.session.get_expiry_date(),
        )
        return JsonResponse({"api_key": _build_api_key_payload(apiKey)})
    except (
        ValidationError,
        PermissionDenied,
        ApiKey.DoesNotExist,
        Membership.DoesNotExist,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_api_key_error_response(e)


@never_cache
@require_POST
@sensitive_variables()
def revoke_account_api_key(
    request: HttpRequest, apiKeyId: uuid.UUID, userId: uuid.UUID | None = None
) -> JsonResponse:
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        emptyRequest = parse_json_request(request, AccountRequest)
        if isinstance(emptyRequest, JsonResponse):
            return emptyRequest
        user = cast(User, request.user)
        apiKey = revoke_api_key(
            actorId=user.id,
            channel=AccessChannel.SESSION,
            userId=user.id if userId is None else userId,
            apiKeyId=apiKeyId,
            sessionAuthHash=request.session.get(HASH_SESSION_KEY, ""),
            sessionExpiresAt=request.session.get_expiry_date(),
            asAdministrator=userId is not None,
        )
        return JsonResponse({"api_key": _build_api_key_payload(apiKey)})
    except (
        ValidationError,
        PermissionDenied,
        ApiKey.DoesNotExist,
        Membership.DoesNotExist,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_api_key_error_response(e)
