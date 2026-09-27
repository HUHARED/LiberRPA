# FileName: views.py
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

from accounts.models import User
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
)

from .contracts import (
    OrganizationSettingsRequest,
    OrganizationSettingsRecordResponse,
    OrganizationSettingsResponse,
)
from .models import Organization
from .permissions import AccessChannel, get_current_membership
from .services import get_organization_settings, update_organization_settings

_INT_MAX_SETTINGS_BODY_BYTES = 32 * 1024


def _build_organization_settings_response(organization: Organization) -> JsonResponse:
    settingsResponse = OrganizationSettingsResponse(
        organization=OrganizationSettingsRecordResponse(
            id=organization.id,
            name=organization.name,
            default_time_zone=organization.default_time_zone,
            notes=organization.notes,
        )
    )
    return JsonResponse(settingsResponse.model_dump(mode="python"))


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_organization_settings(request: HttpRequest) -> JsonResponse:
    """Read or update the signed-in administrator's own organization General settings."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        if request.method == "POST":
            # Allow a complete 2,000-character note, including escaped Unicode text.
            settingsRequest = parse_json_request(
                request,
                OrganizationSettingsRequest,
                maxBodyBytes=_INT_MAX_SETTINGS_BODY_BYTES,
            )
            if isinstance(settingsRequest, JsonResponse):
                return settingsRequest
            organization = update_organization_settings(
                actorId=user.id,
                organizationId=membership.organization_id,
                channel=AccessChannel.SESSION,
                name=settingsRequest.name,
                defaultTimeZone=settingsRequest.default_time_zone,
                notes=settingsRequest.notes,
            )
        else:
            organization = get_organization_settings(
                actorId=user.id,
                organizationId=membership.organization_id,
                channel=AccessChannel.SESSION,
            )
        return _build_organization_settings_response(organization)
    except ValidationError as e:
        return build_error_response(
            "invalid_organization_settings",
            "Some organization settings are invalid.",
            statusCode=400,
            fields=e.message_dict,
        )
    except PermissionDenied:
        return build_error_response(
            "organization_settings_unavailable",
            "Organization settings are unavailable for this account or organization.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
