# FileName: backup_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from accounts.session_revocation import SessionInvalidatedError
from console_project.contracts import JsonRequest
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)

from .access import get_platform_actor
from .audit import record_audit
from .contracts import AuditStage
from .models import AuditScope
from .backup_models import BackupState
from .backup_worker import request_backup, load_backup_status

_LOGGER = logging.getLogger("console.backup")


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_request_backup(request: HttpRequest) -> JsonResponse:
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.GET:
            return build_error_response(
                "invalid_backup_query",
                "This request does not accept query parameters.",
                statusCode=400,
            )
        if request.method == "POST":
            payload = parse_json_request(request, JsonRequest)
            if isinstance(payload, JsonResponse):
                return payload
            with transaction.atomic():
                state, _ = BackupState.objects.select_for_update().get_or_create(pk=1)
                actor = get_platform_actor(request, forUpdate=True)
                record, boolCreated = request_backup(state)
                if boolCreated:
                    record_audit(
                        "backup.request",
                        actor=actor,
                        organization=None,
                        target=record,
                        scope=AuditScope.PLATFORM,
                        stage=AuditStage.REQUEST,
                    )
        response = load_backup_status()
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
            e.code or "backup_unavailable", " ".join(e.messages), statusCode=409
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
    except (ContractValidationError, PydanticSerializationError):
        _LOGGER.exception("Could not build the backup status response.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )
