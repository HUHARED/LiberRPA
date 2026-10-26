# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import logging
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Concatenate, cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError
from console_project.contracts import JsonResponsePayload, MessageResponse
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.http import (
    lock_request_write_access,
    parse_department_resource_filters,
)
from organizations.models import Membership, Department
from organizations.permissions import (
    AccessChannel,
    get_current_membership,
    build_organization_access,
)
from organizations.rate_limits import check_request_budget

from .contracts import (
    AssetType,
    AssetCreationRequest,
    AssetUpdateRequest,
    AssetDeletionRequest,
)
from .models import Asset
from .queries import get_asset_query, get_asset_list, build_asset_details
from .services import (
    SecretStorageUnavailableError,
    create_asset,
    update_asset,
    delete_asset,
)

_LOGGER = logging.getLogger("console.assets")
_INT_MAX_BODY_BYTES = 2 * 1024 * 1024


def _build_asset_response(
    payload: JsonResponsePayload, *, statusCode: int = 200
) -> HttpResponse:
    # Omit unset secret values while preserving an explicitly stored JSON null.
    return HttpResponse(
        payload.model_dump_json(exclude_unset=True),
        status=statusCode,
        content_type="application/json",
    )


def _build_asset_error_response(e: Exception) -> JsonResponse:
    match e:
        case SessionInvalidatedError():
            return build_authentication_required_response()
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
        case (
            ContractValidationError()
            | PydanticSerializationError()
            | json.JSONDecodeError()
        ):
            # Request JSON errors have already been handled at the parsing boundary.
            _LOGGER.exception("Invalid stored asset value or response contract.")
            return build_error_response(
                "internal_server_error",
                "The service could not build a valid response.",
                statusCode=500,
            )
        case _:
            return build_service_unavailable_response()


def _session_asset_view[**P](
    view: Callable[Concatenate[HttpRequest, Membership, P], HttpResponse],
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    """Share session authentication and errors; each view owns parsing and transactions."""

    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        try:
            membership = get_current_membership(actorId=cast(User, request.user).id)
            check_request_budget(request, membership.organization)
            return view(request, membership, *args, **kwargs)
        except (
            PermissionDenied,
            ValidationError,
            Asset.DoesNotExist,
            Department.DoesNotExist,
            InvalidPage,
            SecretStorageUnavailableError,
            ContractValidationError,
            PydanticSerializationError,
            json.JSONDecodeError,
            ImproperlyConfigured,
            DatabaseError,
        ) as e:
            return _build_asset_error_response(e)

    return wrapped


@require_http_methods(["GET", "POST"])
@_session_asset_view
def list_or_create_assets(request: HttpRequest, membership: Membership) -> HttpResponse:
    if request.method == "GET":
        try:
            filters = parse_department_resource_filters(
                request.GET, extraFields=frozenset({"type"})
            )
            listType = request.GET.getlist("type")
            if len(listType) > len(AssetType.values):
                raise ValueError("Invalid asset types.")
            tupleAssetType = tuple(AssetType(strAssetType) for strAssetType in listType)
        except ValueError:
            return build_error_response(
                "invalid_filter",
                "Use a positive page, one name, department UUIDs, and supported asset types.",
                statusCode=400,
            )
        access = build_organization_access(membership, channel=AccessChannel.SESSION)
        return _build_asset_response(
            get_asset_list(access, **filters, assetTypes=tupleAssetType)
        )

    payload = parse_json_request(
        request, AssetCreationRequest, maxBodyBytes=_INT_MAX_BODY_BYTES
    )
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        asset = create_asset(
            access,
            departmentId=payload.department_id,
            name=payload.name,
            notes=payload.notes,
            assetType=payload.asset_type,
            value=payload.value,
        )
        return _build_asset_response(
            MessageResponse(message=f'Asset "{asset.name}" created.'), statusCode=201
        )


@require_http_methods(["GET", "POST"])
@_session_asset_view
def get_or_update_asset(
    request: HttpRequest, membership: Membership, assetId: uuid.UUID
) -> HttpResponse:
    if request.method == "GET":
        access = build_organization_access(membership, channel=AccessChannel.SESSION)
        asset = get_asset_query(access).get(pk=assetId)
        return _build_asset_response(build_asset_details(asset, access))

    payload = parse_json_request(
        request, AssetUpdateRequest, maxBodyBytes=_INT_MAX_BODY_BYTES
    )
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        update_asset(access, assetId, payload)
        return JsonResponse({})


@require_POST
@_session_asset_view
def delete_asset_view(
    request: HttpRequest, membership: Membership, assetId: uuid.UUID
) -> HttpResponse:
    payload = parse_json_request(request, AssetDeletionRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        delete_asset(access, assetId)
        return _build_asset_response(MessageResponse(message="Asset deleted."))
