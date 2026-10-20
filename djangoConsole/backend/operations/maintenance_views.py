# FileName: maintenance_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
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
from .contracts import MaintenanceAction, MaintenanceRequest
from .models import MaintenanceState, AuditScope
from .maintenance import (
    lock_maintenance_state,
    get_resume_block_reason,
    load_maintenance_status,
)

_LOGGER = logging.getLogger("console.operations")


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_maintenance(request: HttpRequest) -> JsonResponse:
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.GET:
            return build_error_response(
                "invalid_maintenance_query",
                "This request does not accept query parameters.",
                statusCode=400,
            )
        if request.method == "POST":
            payload = parse_json_request(request, MaintenanceRequest)
            if isinstance(payload, JsonResponse):
                return payload
            with transaction.atomic():
                state = lock_maintenance_state(forUpdate=True)
                actor = get_platform_actor(request, forUpdate=True)
                if state is None:
                    state = MaintenanceState.objects.create(pk=1)
                boolEnter = payload.action == MaintenanceAction.ENTER
                if boolEnter != (state.entered_at is not None):
                    if not boolEnter:
                        strReason = get_resume_block_reason()
                        if strReason:
                            raise ValidationError(strReason, code="service_not_ready")
                    dictBefore = get_audit_snapshot(state)
                    state.entered_at = timezone.now() if boolEnter else None
                    state.save(update_fields=["entered_at"])
                    record_audit(
                        "maintenance.enter" if boolEnter else "maintenance.resume",
                        actor=actor,
                        organization=None,
                        target=state,
                        before=dictBefore,
                        scope=AuditScope.PLATFORM,
                    )
        response = load_maintenance_status()
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
    except ValidationError as e:
        return build_error_response(
            e.code or "invalid_maintenance_action", " ".join(e.messages), statusCode=409
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
    except (ContractValidationError, PydanticSerializationError):
        _LOGGER.exception("Could not build the maintenance response.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )


@never_cache
@require_GET
def get_run_activity(request: HttpRequest) -> JsonResponse:
    from .run_activity import load_run_activity

    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.GET:
            return build_error_response(
                "invalid_run_activity_query",
                "This request does not accept query parameters.",
                statusCode=400,
            )
        response = load_run_activity()
        return JsonResponse(response.model_dump(mode="python"))
    except PermissionDenied:
        return build_error_response(
            "platform_access_required",
            "Platform administrator access is required.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
    except (ContractValidationError, PydanticSerializationError):
        _LOGGER.exception("Could not build the run activity response.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )
