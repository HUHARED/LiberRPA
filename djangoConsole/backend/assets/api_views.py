# FileName: api_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Concatenate

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from accounts.api_key_authentication import InvalidApiKeyError
from accounts.resource_authentication import (
    InvalidResourceCredentialError,
    ResourceAuthenticationContext,
    lock_resource_write_access,
    build_resource_authentication_required_response,
    authenticate_resource_request,
)
from console_project.contracts import JsonRequest, JsonResponsePayload
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.models import Department
from organizations.rate_limits import RequestBudget, request_budget
from organizations.validators import parse_resource_path

from .contracts import (
    MAX_ASSET_RUNTIME_BYTES,
    AssetType,
    AssetPathRequest,
    AssetRuntimeValueRequest,
)
from .models import Asset
from .runtime import (
    AssetRuntimeError,
    get_runtime_asset_value,
    set_runtime_asset_value,
    get_runtime_secret_value,
)
from .services import SecretStorageUnavailableError

_LOGGER = logging.getLogger("console.assets")


def _api_asset_view[**P](
    view: Callable[
        Concatenate[HttpRequest, ResourceAuthenticationContext, P], HttpResponse
    ],
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    @csrf_exempt
    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        try:
            authentication = authenticate_resource_request(request)
            if isinstance(authentication, JsonResponse):
                return authentication
            return view(request, authentication, *args, **kwargs)
        except (InvalidApiKeyError, InvalidResourceCredentialError):
            return build_resource_authentication_required_response()
        except PermissionDenied:
            return build_error_response(
                "asset_access_required", "Asset access is unavailable.", statusCode=403
            )
        except (Asset.DoesNotExist, Department.DoesNotExist):
            return build_error_response(
                "asset_not_found",
                "The asset or department is unavailable.",
                statusCode=404,
            )
        except AssetRuntimeError as e:
            return build_error_response(e.code, str(e), statusCode=409)
        except ValidationError as e:
            return build_error_response(
                "invalid_asset",
                "Some asset fields are invalid.",
                statusCode=400,
                fields=e.message_dict
                if hasattr(e, "error_dict")
                else {"__all__": e.messages},
            )
        except SecretStorageUnavailableError:
            return build_error_response(
                "secret_storage_unavailable",
                "Secret storage is unavailable. Ask the Console administrator to check encryption keys.",
                statusCode=503,
            )
        except (
            ContractValidationError,
            PydanticSerializationError,
            json.JSONDecodeError,
        ):
            # Validation exceptions can contain secret values. Do not log their text or traceback.
            _LOGGER.error("Invalid stored asset value or runtime response contract.")
            return build_error_response(
                "internal_server_error",
                "The service could not build a valid response.",
                statusCode=500,
            )
        except (DatabaseError, ImproperlyConfigured):
            return build_service_unavailable_response()

    return wrapped


@sensitive_variables()
def _parse_asset_request[Payload: JsonRequest](
    request: HttpRequest, requestSchema: type[Payload]
) -> Payload | JsonResponse:
    if request.GET:
        return build_error_response(
            "invalid_request",
            "Use the request body; query parameters are not accepted.",
            statusCode=400,
        )
    return parse_json_request(
        request, requestSchema, maxBodyBytes=MAX_ASSET_RUNTIME_BYTES
    )


@sensitive_variables()
def _build_asset_response(payload: JsonResponsePayload) -> HttpResponse:
    responseBytes = payload.model_dump_json().encode("utf-8")
    if len(responseBytes) > MAX_ASSET_RUNTIME_BYTES:
        raise AssetRuntimeError(
            "asset_response_too_large", "The response exceeds the byte limit."
        )
    return HttpResponse(responseBytes, content_type="application/json")


@require_POST
@_api_asset_view
@request_budget(RequestBudget.READ)
def get_asset_value(
    request: HttpRequest, authentication: ResourceAuthenticationContext
) -> HttpResponse:
    payload = _parse_asset_request(request, AssetPathRequest)
    if isinstance(payload, JsonResponse):
        return payload
    return _build_asset_response(
        get_runtime_asset_value(authentication.access, parse_resource_path(payload.path))
    )


@require_POST
@_api_asset_view
def set_asset_value(
    request: HttpRequest, authentication: ResourceAuthenticationContext
) -> HttpResponse:
    payload = _parse_asset_request(request, AssetRuntimeValueRequest)
    if isinstance(payload, JsonResponse):
        return payload
    assetPathParts = parse_resource_path(payload.path)
    with transaction.atomic():
        access = lock_resource_write_access(authentication)
        return _build_asset_response(
            set_runtime_asset_value(
                access, assetPathParts, payload.value, apiKeyId=authentication.apiKeyId
            )
        )


@require_POST
@_api_asset_view
@request_budget(RequestBudget.READ)
def get_asset_secret_text(
    request: HttpRequest, authentication: ResourceAuthenticationContext
) -> HttpResponse:
    payload = _parse_asset_request(request, AssetPathRequest)
    if isinstance(payload, JsonResponse):
        return payload
    return _build_asset_response(
        get_runtime_secret_value(
            authentication.access,
            parse_resource_path(payload.path),
            AssetType.SECRET_TEXT,
        )
    )


@require_POST
@_api_asset_view
@request_budget(RequestBudget.READ)
def get_asset_credential(
    request: HttpRequest, authentication: ResourceAuthenticationContext
) -> HttpResponse:
    payload = _parse_asset_request(request, AssetPathRequest)
    if isinstance(payload, JsonResponse):
        return payload
    return _build_asset_response(
        get_runtime_secret_value(
            authentication.access, parse_resource_path(payload.path), AssetType.CREDENTIAL
        )
    )
