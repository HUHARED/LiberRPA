# FileName: email_change_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_POST
from pydantic import SecretStr

from organizations.permissions import AccessChannel

from .email_changes import (
    EmailChangeCooldownError,
    confirm_email_change,
    get_email_change_info,
    request_email_change,
)
from .http import (
    AccountRequest,
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)
from .models import User
from .rate_limits import (
    reserve_email_change_email_request,
    reserve_email_change_token_request,
)
from .session_revocation import SessionInvalidatedError


class EmailChangeEmailRequest(AccountRequest):
    current_password: SecretStr
    new_email: str


class EmailChangeTokenRequest(AccountRequest):
    token: SecretStr


def _build_email_change_validation_response(
    validationError: ValidationError,
) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        return build_error_response(
            "invalid_email_change",
            "Some email change fields are invalid.",
            statusCode=400,
            fields=validationError.message_dict,
        )
    errorCode = validationError.error_list[0].code or "invalid_email_change"
    return build_error_response(
        errorCode,
        " ".join(validationError.messages),
        statusCode=409 if errorCode == "email_already_registered" else 400,
    )


@never_cache
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def queue_email_change_verification(request: HttpRequest) -> JsonResponse:
    """Authorize a new destination using the current account's session and password."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        changeRequest = parse_json_request(request, EmailChangeEmailRequest)
        if isinstance(changeRequest, JsonResponse):
            return changeRequest
        retryAfterSeconds = reserve_email_change_email_request(
            request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)

        with transaction.atomic():
            request_email_change(
                actorId=user.id,
                channel=AccessChannel.SESSION,
                currentPassword=changeRequest.current_password.get_secret_value(),
                newEmail=changeRequest.new_email,
                sessionAuthHash=cast(str, request.session.get(HASH_SESSION_KEY, "")),
            )
            if request.session.get_expiry_date() <= timezone.now():
                raise SessionInvalidatedError("The current session has expired.")
        return JsonResponse({"message": "Verification email queued."}, status=202)
    except EmailChangeCooldownError as e:
        return build_rate_limited_response(e.retryAfterSeconds)
    except SessionInvalidatedError:
        return build_error_response(
            "authentication_required",
            "The current session is no longer valid. Sign in again.",
            statusCode=401,
        )
    except ValidationError as e:
        return _build_email_change_validation_response(e)
    except PermissionDenied:
        return build_error_response(
            "email_change_unavailable",
            "This email change is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_POST
@sensitive_variables()
def check_email_change_link(request: HttpRequest) -> JsonResponse:
    """Display the new address without confirming it or creating a login session."""
    changeRequest = parse_json_request(request, EmailChangeTokenRequest)
    if isinstance(changeRequest, JsonResponse):
        return changeRequest
    try:
        token = changeRequest.token.get_secret_value()
        retryAfterSeconds = reserve_email_change_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)
        linkInfo = get_email_change_info(token)
        return JsonResponse({
            "new_email": linkInfo.newEmail,
            "expires_at": linkInfo.expiresAt,
        })
    except ValidationError as e:
        return _build_email_change_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_POST
@sensitive_variables()
def confirm_account_email_change(request: HttpRequest) -> JsonResponse:
    """Apply the email proof to its original account, independently of this browser's identity."""
    changeRequest = parse_json_request(request, EmailChangeTokenRequest)
    if isinstance(changeRequest, JsonResponse):
        return changeRequest
    try:
        token = changeRequest.token.get_secret_value()
        retryAfterSeconds = reserve_email_change_token_request(
            request.META.get("REMOTE_ADDR", ""), token=token
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)
        confirm_email_change(token)
        return JsonResponse({"message": "Email changed."})
    except ValidationError as e:
        return _build_email_change_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
