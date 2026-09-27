# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import Literal, cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError, lock_session_write_access
from console_project.contracts import MessageResponse
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.http import parse_department_resource_filters
from organizations.models import Department
from organizations.permissions import (
    AccessChannel,
    get_current_membership,
    resolve_organization_access,
)

from .contracts import (
    AssetDetailsRequest,
    AssetCreationRequest,
    AssetValueRequest,
    AssetDeletionRequest,
    AssetListResponse,
    AssetDetailsResponse,
)
from .models import Asset, AssetType
from .queries import get_asset_query, build_asset_payloads, get_asset_list
from .services import (
    SecretStorageUnavailableError,
    create_asset,
    update_asset_details,
    update_asset_value,
    delete_asset,
)

_INT_MAX_BODY_BYTES = 2 * 1024 * 1024


def _build_asset_error_response(e: Exception) -> JsonResponse:
    match e:
        case SessionInvalidatedError():
            return build_error_response(
                "authentication_required", "Sign in again to continue.", statusCode=401
            )
        case PermissionDenied():
            return build_error_response(
                "asset_access_required", "Asset access is unavailable.", statusCode=403
            )
        case Asset.DoesNotExist() | Department.DoesNotExist():
            return build_error_response(
                "asset_not_found",
                "The asset or department is unavailable.",
                statusCode=404,
            )
        case InvalidPage():
            return build_error_response(
                "invalid_page", "The requested page is unavailable.", statusCode=400
            )
        case SecretStorageUnavailableError():
            return build_error_response(
                "secret_storage_unavailable",
                "Secret storage is not configured. Ask the Console administrator to configure encryption keys.",
                statusCode=503,
            )
        case ValidationError():
            if getattr(e, "code", None) == "asset_count_limit":
                return build_error_response(
                    "asset_count_limit", e.messages[0], statusCode=409
                )
            boolDuplicate = any(
                error.code == "duplicate_asset_name"
                for errors in getattr(e, "error_dict", {}).values()
                for error in errors
            )
            return build_error_response(
                "duplicate_asset_name" if boolDuplicate else "invalid_asset",
                "Some asset fields are invalid.",
                statusCode=409 if boolDuplicate else 400,
                fields=e.message_dict
                if hasattr(e, "error_dict")
                else {"__all__": e.messages},
            )
        case _:
            return build_service_unavailable_response()


@never_cache
@sensitive_variables()
def asset_request(
    request: HttpRequest,
    *,
    action: Literal["list", "details", "value", "delete"],
    assetId: uuid.UUID | None = None,
) -> HttpResponse:
    listMethod = ["GET", "POST"] if action in ("list", "details") else ["POST"]
    if request.method not in listMethod:
        return HttpResponseNotAllowed(listMethod)
    if not request.user.is_authenticated:
        return build_error_response(
            "authentication_required", "Sign in to continue.", statusCode=401
        )
    try:
        membership = get_current_membership(actorId=cast(User, request.user).id)
        with transaction.atomic():
            if request.method == "GET":
                access = resolve_organization_access(
                    actorId=membership.user_id,
                    organizationId=membership.organization_id,
                    channel=AccessChannel.SESSION,
                )
                if action == "list":
                    try:
                        filters = parse_department_resource_filters(
                            request.GET, extraFields=frozenset({"type"})
                        )
                        listType = request.GET.getlist("type")
                        if len(listType) > len(AssetType.values) or any(
                            value not in AssetType.values for value in listType
                        ):
                            raise ValueError("Invalid asset types.")
                    except ValueError:
                        return build_error_response(
                            "invalid_filter",
                            "Use a positive page, one name, department UUIDs, and supported asset types.",
                            statusCode=400,
                        )
                    payload = get_asset_list(
                        access, **filters, assetTypes=tuple(listType)
                    )
                    return JsonResponse(
                        AssetListResponse.model_validate(payload).model_dump(
                            mode="python"
                        )
                    )
                asset = get_asset_query(access).get(pk=assetId)
            else:
                access = lock_session_write_access(
                    membership.user_id,
                    membership.organization_id,
                    AccessChannel.SESSION,
                    request.session.get(HASH_SESSION_KEY, ""),
                    request.session.get_expiry_date(),
                )
                match action:
                    case "list":
                        payload = parse_json_request(
                            request,
                            AssetCreationRequest,
                            maxBodyBytes=_INT_MAX_BODY_BYTES,
                        )
                        if isinstance(payload, JsonResponse):
                            return payload
                        asset = create_asset(
                            access,
                            departmentId=payload.department_id,
                            name=payload.name,
                            notes=payload.notes,
                            assetType=payload.asset_type,
                            value=payload.value,
                        )
                    case "details":
                        assert assetId is not None
                        payload = parse_json_request(
                            request, AssetDetailsRequest, maxBodyBytes=16384
                        )
                        if isinstance(payload, JsonResponse):
                            return payload
                        asset = update_asset_details(
                            access, assetId, name=payload.name, notes=payload.notes
                        )
                    case "value":
                        assert assetId is not None
                        payload = parse_json_request(
                            request, AssetValueRequest, maxBodyBytes=_INT_MAX_BODY_BYTES
                        )
                        if isinstance(payload, JsonResponse):
                            return payload
                        asset = update_asset_value(access, assetId, value=payload.value)
                    case "delete":
                        assert assetId is not None
                        payload = parse_json_request(request, AssetDeletionRequest)
                        if isinstance(payload, JsonResponse):
                            return payload
                        delete_asset(access, assetId)
                        return JsonResponse(
                            MessageResponse(message="Asset deleted.").model_dump()
                        )
            payload = {
                "asset": build_asset_payloads([asset], access, includeValue=True)[0]
            }
            return JsonResponse(
                AssetDetailsResponse.model_validate(payload).model_dump(
                    mode="python", exclude_unset=True
                ),
                status=201 if request.method == "POST" and action == "list" else 200,
            )
    except (
        SessionInvalidatedError,
        PermissionDenied,
        ValidationError,
        Asset.DoesNotExist,
        Department.DoesNotExist,
        InvalidPage,
        SecretStorageUnavailableError,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_asset_error_response(e)
