# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError
from console_project.contracts import MessageResponse
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)

from .contracts import (
    OrganizationRetentionRequest,
    OrganizationSettingsRequest,
    OrganizationSettingsRecordResponse,
    OrganizationSettingsResponse,
)
from .models import Organization
from .http import lock_request_write_access
from .permissions import (
    AccessChannel,
    get_current_membership,
    require_organization_business_available,
)
from .rate_limits import check_request_budget
from .services import (
    get_organization_settings,
    update_organization_settings,
    update_organization_retention,
)
from .usage import get_organization_usage

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
@require_GET
def get_current_organization_usage(request: HttpRequest) -> JsonResponse:
    """Let current OrgAdmins inspect effective limits without changing platform policy."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        membership = get_current_membership(actorId=cast(User, request.user).pk)
        if not membership.is_org_admin:
            raise PermissionDenied("Organization administrator access is required.")
        require_organization_business_available(membership.organization)
        check_request_budget(request, membership.organization)
        return JsonResponse(
            get_organization_usage(membership.organization).model_dump(mode="python")
        )
    except PermissionDenied:
        return build_error_response(
            "organization_usage_unavailable",
            "Organization usage is unavailable for this account or organization.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_POST
def update_current_organization_retention(request: HttpRequest) -> JsonResponse:
    """Save only Run Log Retention for the signed-in organization administrator."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        membership = get_current_membership(actorId=cast(User, request.user).pk)
        check_request_budget(request, membership.organization)
        retentionRequest = parse_json_request(request, OrganizationRetentionRequest)
        if isinstance(retentionRequest, JsonResponse):
            return retentionRequest
        with transaction.atomic():
            access = lock_request_write_access(request, membership)
            update_organization_retention(
                access=access, runLogDays=retentionRequest.run_log_days
            )
        return JsonResponse(
            MessageResponse(message="Retention saved.").model_dump(mode="python")
        )
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except ValidationError as e:
        return build_error_response(
            "invalid_organization_retention",
            "Run Log Retention is invalid.",
            statusCode=400,
            fields=e.message_dict,
        )
    except PermissionDenied:
        return build_error_response(
            "organization_retention_unavailable",
            "Retention settings are unavailable for this account or organization.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_organization_settings(request: HttpRequest) -> JsonResponse:
    """Read or update the signed-in administrator's own organization General settings."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        check_request_budget(request, membership.organization)
        if request.method == "POST":
            # Allow a complete 2,000-character note, including escaped Unicode text.
            settingsRequest = parse_json_request(
                request,
                OrganizationSettingsRequest,
                maxBodyBytes=_INT_MAX_SETTINGS_BODY_BYTES,
            )
            if isinstance(settingsRequest, JsonResponse):
                return settingsRequest
            with transaction.atomic():
                access = lock_request_write_access(request, membership)
                organization = update_organization_settings(
                    access=access,
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
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
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
