# FileName: account_deletion_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from copy import deepcopy
from typing import cast

from django.contrib.auth import HASH_SESSION_KEY, logout
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods

from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)
from organizations.models import Membership
from organizations.permissions import AccessChannel

from .account_deletion import (
    AccountDeletionInfo,
    delete_account,
    get_account_deletion_info,
)
from .contracts import AccountDeletionRequest, AccountDeletionPreviewResponse
from .models import User
from .rate_limits import reserve_account_deletion_request
from .session_revocation import SessionInvalidatedError


def _build_account_deletion_payload(
    deletionInfo: AccountDeletionInfo,
) -> dict[str, object]:
    return AccountDeletionPreviewResponse.model_validate({
        "user": {
            "id": deletionInfo.userId,
            "email": deletionInfo.email,
            "username": deletionInfo.username,
        },
        "can_delete": deletionInfo.canDelete,
        "blockers": [{"code": "last_org_admin"}] if deletionInfo.isLastOrgAdmin else [],
    }).model_dump(mode="python")


def _build_deletion_validation_response(validationError: ValidationError) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        return build_error_response(
            "invalid_account_deletion",
            "The current password is incorrect.",
            statusCode=400,
            fields=validationError.message_dict,
        )
    strErrorCode = validationError.error_list[0].code or "invalid_account_deletion"
    return build_error_response(
        strErrorCode,
        " ".join(validationError.messages),
        statusCode=409 if strErrorCode == "last_org_admin" else 400,
    )


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
@sensitive_variables()
def get_or_delete_account(
    request: HttpRequest, userId: uuid.UUID | None = None
) -> JsonResponse:
    """Preview or delete the current account, or a different member through the admin route."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        boolOwnAccount = userId is None
        if userId == user.id:
            return build_error_response(
                "use_profile_deletion",
                "Delete your own account from My Profile.",
                statusCode=400,
            )
        targetId = user.id if userId is None else userId
        if request.method == "GET":
            deletionInfo = get_account_deletion_info(
                actorId=user.id, channel=AccessChannel.SESSION, userId=targetId
            )
            return JsonResponse(_build_account_deletion_payload(deletionInfo))

        deletionRequest = parse_json_request(request, AccountDeletionRequest)
        if isinstance(deletionRequest, JsonResponse):
            return deletionRequest
        intRetryAfterSeconds = reserve_account_deletion_request(
            request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)

        strSessionAuthHash = cast(str, request.session.get(HASH_SESSION_KEY, ""))
        previousSession = deepcopy(request.session) if boolOwnAccount else None
        try:
            with transaction.atomic():
                delete_account(
                    actorId=user.id,
                    channel=AccessChannel.SESSION,
                    userId=targetId,
                    currentPassword=deletionRequest.current_password.get_secret_value(),
                    sessionAuthHash=strSessionAuthHash,
                )
                if request.session.get_expiry_date() <= timezone.now():
                    raise SessionInvalidatedError("The current session has expired.")
                if boolOwnAccount:
                    logout(request)
        except Exception:
            # Rollback restores stored sessions; also restore the browser request after logout cleared it in memory.
            if previousSession is not None:
                request.session = previousSession
                request.user = user
            raise
        return JsonResponse({
            "message": "Account deleted. Sign in again."
            if boolOwnAccount
            else "Account deleted."
        })
    except SessionInvalidatedError:
        return build_error_response(
            "authentication_required",
            "The current session is no longer valid. Sign in again.",
            statusCode=401,
        )
    except ValidationError as e:
        return _build_deletion_validation_response(e)
    except (Membership.DoesNotExist, User.DoesNotExist):
        return build_error_response(
            "member_not_found", "Member not found or unavailable.", statusCode=404
        )
    except PermissionDenied:
        return build_error_response(
            "account_deletion_unavailable",
            "This account deletion is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
