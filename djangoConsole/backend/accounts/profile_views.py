# FileName: profile_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)
from console_project.validators import validate_time_zone
from operations.access import get_platform_actor
from operations.contracts import AuditAction
from operations.audit import get_audit_snapshot, record_audit
from operations.models import AuditScope
from organizations.access_info import get_account_access_info
from organizations.http import build_account_access_payload, get_request_access
from organizations.rate_limits import RequestBudget, request_budget

from .contracts import (
    SessionUserResponse,
    ProfileUpdateRequest,
    PlatformTimeZoneRequest,
    ProfileWriteResponse,
)
from .models import User
from .session_revocation import SessionInvalidatedError
from .profile import update_profile


def _build_profile_response(user: User) -> ProfileWriteResponse:
    return ProfileWriteResponse(
        user=SessionUserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            platform_login=user.platform_login,
            time_zone=user.time_zone,
            is_platform_admin=user.is_platform_admin,
        )
    )


@never_cache
@require_http_methods(["GET", "POST"])
@request_budget(RequestBudget.INDEPENDENT)
def get_or_update_profile(request: HttpRequest) -> JsonResponse:
    """Read the signed-in account's profile or save only its two editable fields."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        if request.method == "POST":
            profileRequest = parse_json_request(request, ProfileUpdateRequest)
            if isinstance(profileRequest, JsonResponse):
                return profileRequest
            with transaction.atomic():
                access = get_request_access(request, forUpdate=True)
                user = update_profile(
                    access=access,
                    username=profileRequest.username,
                    timeZone=profileRequest.time_zone,
                )
            # Return the saved fields without making unrelated reads after the commit.
            return JsonResponse(_build_profile_response(user).model_dump(mode="python"))

        accountAccessInfo = get_account_access_info(actorId=user.id)
        return JsonResponse({
            **_build_profile_response(user).model_dump(mode="python"),
            **build_account_access_payload(accountAccessInfo),
        })
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
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


@never_cache
@require_POST
def update_platform_time_zone(request: HttpRequest) -> JsonResponse:
    """Save only the platform administrator's display time zone."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.GET:
            return build_error_response(
                "invalid_profile_query",
                "This request does not accept query parameters.",
                statusCode=400,
            )
        payload = parse_json_request(request, PlatformTimeZoneRequest)
        if isinstance(payload, JsonResponse):
            return payload
        validate_time_zone(payload.time_zone)

        with transaction.atomic():
            actor = get_platform_actor(request, forUpdate=True)
            if actor.time_zone != payload.time_zone:
                dictBefore = get_audit_snapshot(actor)
                actor.time_zone = payload.time_zone
                actor.save(update_fields=["time_zone"])
                record_audit(
                    AuditAction.ACCOUNT_UPDATE_PROFILE,
                    actor=actor,
                    organization=None,
                    target=actor,
                    before=dictBefore,
                    scope=AuditScope.PLATFORM,
                )
        return JsonResponse(_build_profile_response(actor).model_dump(mode="python"))
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except PermissionDenied:
        return build_error_response(
            "platform_access_required",
            "Platform administrator access is required.",
            statusCode=403,
        )
    except ValidationError as e:
        return build_error_response(
            "invalid_profile",
            "Select a valid time zone.",
            statusCode=400,
            fields={"time_zone": e.messages},
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
