# FileName: service_settings_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from accounts.session_revocation import SessionInvalidatedError
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)

from .access import get_platform_actor
from .audit import get_audit_snapshot, record_audit
from .contracts import AuditAction, ServiceSettingsRequest, ServiceSettingsResponse
from .models import ServiceSettings, AuditScope

_LOGGER = logging.getLogger("console.operations")


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_service_settings(request: HttpRequest) -> JsonResponse:
    """Manage the registration policy without exposing deployment configuration writes."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.GET:
            return build_error_response(
                "invalid_service_settings_query",
                "This request does not accept query parameters.",
                statusCode=400,
            )

        if request.method == "POST":
            payload = parse_json_request(request, ServiceSettingsRequest)
            if isinstance(payload, JsonResponse):
                return payload
            with transaction.atomic():
                serviceSettings, _ = (
                    ServiceSettings.objects.select_for_update().get_or_create(pk=1)
                )
                actor = get_platform_actor(request, forUpdate=True)
                if (
                    serviceSettings.allow_organization_creation
                    != payload.allow_organization_creation
                ):
                    dictBefore = get_audit_snapshot(serviceSettings)
                    serviceSettings.allow_organization_creation = (
                        payload.allow_organization_creation
                    )
                    serviceSettings.save(update_fields=["allow_organization_creation"])
                    record_audit(
                        AuditAction.SERVICE_SETTINGS_UPDATE,
                        actor=actor,
                        organization=None,
                        target=serviceSettings,
                        before=dictBefore,
                        scope=AuditScope.PLATFORM,
                    )
        else:
            serviceSettings = ServiceSettings.objects.filter(pk=1).first()
            if serviceSettings is None:
                serviceSettings = ServiceSettings()

        response = ServiceSettingsResponse(
            allow_organization_creation=serviceSettings.allow_organization_creation,
            console_url=settings.CONSOLE_URL,
            support_email=settings.CONSOLE_SUPPORT_EMAIL,
        )
        return JsonResponse(response.model_dump(mode="python"))
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
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
    except (ContractValidationError, PydanticSerializationError):
        _LOGGER.exception("Could not build the service settings response.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )
