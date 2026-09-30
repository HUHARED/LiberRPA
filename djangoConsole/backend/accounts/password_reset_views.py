# FileName: password_reset_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.contrib.auth import logout
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_POST
from pydantic import SecretStr

from console_project.contracts import JsonRequest
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)

from .password_resets import (
    complete_password_reset,
    get_password_reset_info,
    request_password_reset_email,
)
from .rate_limits import (
    apply_password_reset_email_rate_limit,
    apply_password_reset_token_rate_limit,
)


class PasswordResetEmailRequest(JsonRequest):
    email: str


class PasswordResetTokenRequest(JsonRequest):
    token: SecretStr


class PasswordResetCompletionRequest(PasswordResetTokenRequest):
    new_password: SecretStr
    confirm_password: SecretStr


def _build_reset_validation_response(validationError: ValidationError) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        return build_error_response(
            "invalid_password_reset",
            "Some password fields are invalid.",
            statusCode=400,
            fields=validationError.message_dict,
        )
    return build_error_response(
        "invalid_password_reset_token",
        "The password reset link is invalid or expired.",
        statusCode=400,
    )


@never_cache
@require_POST
@sensitive_variables()
def queue_password_reset_email(request: HttpRequest) -> JsonResponse:
    """Accept recovery requests without revealing account, cooldown, or delivery state."""
    resetRequest = parse_json_request(request, PasswordResetEmailRequest)
    if isinstance(resetRequest, JsonResponse):
        return resetRequest
    try:
        intRetryAfterSeconds = apply_password_reset_email_rate_limit(
            request.META.get("REMOTE_ADDR", "")
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        request_password_reset_email(resetRequest.email)
    except ValidationError:
        return build_error_response(
            "invalid_email", "Enter a valid email address.", statusCode=400
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
    return JsonResponse(
        {"message": "If this address is eligible, a password reset email will be sent."},
        status=202,
    )


@never_cache
@require_POST
@sensitive_variables()
def check_password_reset_link(request: HttpRequest) -> JsonResponse:
    """Read a valid proof without consuming it; opening the email link cannot reset a password."""
    resetRequest = parse_json_request(request, PasswordResetTokenRequest)
    if isinstance(resetRequest, JsonResponse):
        return resetRequest
    try:
        strToken = resetRequest.token.get_secret_value()
        intRetryAfterSeconds = apply_password_reset_token_rate_limit(
            request.META.get("REMOTE_ADDR", ""), token=strToken
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        linkInfo = get_password_reset_info(strToken)
        return JsonResponse({"email": linkInfo.email, "expires_at": linkInfo.expiresAt})
    except ValidationError as e:
        return _build_reset_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def reset_account_password(request: HttpRequest) -> JsonResponse:
    """Use the email proof's account identity and return to normal sign-in after success."""
    resetRequest = parse_json_request(request, PasswordResetCompletionRequest)
    if isinstance(resetRequest, JsonResponse):
        return resetRequest
    try:
        strToken = resetRequest.token.get_secret_value()
        intRetryAfterSeconds = apply_password_reset_token_rate_limit(
            request.META.get("REMOTE_ADDR", ""), token=strToken
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        if resetRequest.new_password != resetRequest.confirm_password:
            raise ValidationError({"confirm_password": "The new passwords do not match."})

        currentUserId = request.user.pk if request.user.is_authenticated else None
        with transaction.atomic():
            user = complete_password_reset(
                token=strToken, newPassword=resetRequest.new_password.get_secret_value()
            )
            # A browser signed in to a different account must not select or lose that account.
            if currentUserId == user.id:
                logout(request)
        return JsonResponse({"message": "Password reset. Sign in again."})
    except ValidationError as e:
        return _build_reset_validation_response(e)
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
