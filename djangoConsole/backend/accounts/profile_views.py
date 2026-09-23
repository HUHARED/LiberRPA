# FileName: profile_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from organizations.access import get_account_access_info
from organizations.http import build_account_access_payload
from organizations.permissions import AccessChannel

from .http import (
    AccountRequest,
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
)
from .models import User
from .profile import update_profile


class ProfileUpdateRequest(AccountRequest):
    username: str
    time_zone: str


def _build_profile_user_payload(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "time_zone": user.time_zone,
    }


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_profile(request: HttpRequest) -> JsonResponse:
    """Read the signed-in account's profile or save only its two editable fields."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        if request.method == "POST":
            profileRequest = parse_json_request(request, ProfileUpdateRequest)
            if isinstance(profileRequest, JsonResponse):
                return profileRequest
            user = update_profile(
                actorId=user.id,
                channel=AccessChannel.SESSION,
                username=profileRequest.username,
                timeZone=profileRequest.time_zone,
            )
            # Return the saved fields without making unrelated reads after the commit.
            return JsonResponse({"user": _build_profile_user_payload(user)})

        accountAccessInfo = get_account_access_info(actorId=user.id)
        return JsonResponse({
            "user": _build_profile_user_payload(user),
            **build_account_access_payload(accountAccessInfo),
        })
    except ValidationError as e:
        return build_error_response(
            "invalid_profile",
            "Some profile fields are invalid.",
            statusCode=400,
            fields=e.message_dict,
        )
    except PermissionDenied:
        return build_error_response(
            "profile_unavailable",
            "This profile operation is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
