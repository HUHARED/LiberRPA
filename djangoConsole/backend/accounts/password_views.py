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

from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)
from organizations.http import get_request_access

from .contracts import PasswordChangeRequest
from .models import User
from .session_revocation import SessionInvalidatedError
from .password_changes import change_password
from .rate_limits import apply_password_change_rate_limit


@never_cache
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def change_account_password(request: HttpRequest) -> JsonResponse:
    """Change the current account's password and require every old web session to sign in again."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        passwordRequest = parse_json_request(request, PasswordChangeRequest)
        if isinstance(passwordRequest, JsonResponse):
            return passwordRequest

        intRetryAfterSeconds = apply_password_change_rate_limit(
            request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)

        if passwordRequest.new_password != passwordRequest.confirm_password:
            raise ValidationError({"confirm_password": "The new passwords do not match."})

        # Commit the password change and current session removal together.
        with transaction.atomic():
            access = get_request_access(request, forUpdate=True)
            change_password(
                access=access,
                currentPassword=passwordRequest.current_password.get_secret_value(),
                newPassword=passwordRequest.new_password.get_secret_value(),
            )
            logout(request)
        return JsonResponse({"message": "Password changed. Sign in again."})
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except ValidationError as e:
        return build_error_response(
            "invalid_password_change",
            "Some password fields are invalid.",
            statusCode=400,
            fields=e.message_dict,
        )
    except PermissionDenied:
        return build_error_response(
            "password_change_unavailable",
            "This password change is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
