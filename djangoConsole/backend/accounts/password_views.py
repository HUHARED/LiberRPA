# FileName: password_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.contrib.auth import logout
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_POST
from pydantic import SecretStr

from organizations.permissions import AccessChannel

from .http import (
    AccountRequest,
    build_error_response,
    build_rate_limited_response,
    parse_json_request,
)
from .models import User
from .password_changes import change_password
from .rate_limits import reserve_password_change_request


class PasswordChangeRequest(AccountRequest):
    current_password: SecretStr
    new_password: SecretStr
    confirm_password: SecretStr


@never_cache
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def change_account_password(request: HttpRequest) -> JsonResponse:
    """Change the current account's password and require every old web session to sign in again."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        passwordRequest = parse_json_request(request, PasswordChangeRequest)
        if isinstance(passwordRequest, JsonResponse):
            return passwordRequest

        retryAfterSeconds = reserve_password_change_request(
            request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)

        if passwordRequest.new_password != passwordRequest.confirm_password:
            raise ValidationError({"confirm_password": "The new passwords do not match."})

        # Commit the password change and current session removal together.
        with transaction.atomic():
            change_password(
                actorId=user.id,
                channel=AccessChannel.SESSION,
                currentPassword=passwordRequest.current_password.get_secret_value(),
                newPassword=passwordRequest.new_password.get_secret_value(),
            )
            logout(request)
        return JsonResponse({"message": "Password changed. Sign in again."})
    except ValidationError as e:
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_password_change",
                    "message": "Some password fields are invalid.",
                    "fields": e.message_dict,
                }
            },
            status=400,
        )
    except PermissionDenied:
        return build_error_response(
            "password_change_unavailable",
            "This password change is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )
