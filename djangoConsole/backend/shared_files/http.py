# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import logging
from collections.abc import Callable
from functools import wraps
from typing import Concatenate, cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from pydantic import ValidationError as ContractValidationError

from accounts.models import User
from accounts.api_key_authentication import (
    InvalidApiKeyError,
    ApiKeyAuthenticationContext,
    authenticate_api_key,
    lock_api_key_write_access,
)
from accounts.rate_limits import apply_api_key_authentication_rate_limit
from accounts.session_revocation import SessionInvalidatedError, lock_session_write_access
from console_project.contracts import JsonRequest, JsonResponsePayload
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)
from file_storage.models import DownloadSession
from file_storage.services import FileOperationError
from organizations.models import Membership, Department
from organizations.validators import normalize_path_name
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    resolve_organization_access,
)

from .contracts import MAX_FILE_RESPONSE_BYTES, UPLOAD_CHUNK_BYTES
from .models import SharedFile, UploadSession

_LOGGER = logging.getLogger("console.shared_files")

type FileAuthentication = Membership | ApiKeyAuthenticationContext


class FileRequestError(Exception):
    """Malformed HTTP parameters, not an internal response or persistence error."""


_HANDLED_ERRORS = (
    PermissionDenied,
    InvalidApiKeyError,
    SharedFile.DoesNotExist,
    Department.DoesNotExist,
    UploadSession.DoesNotExist,
    DownloadSession.DoesNotExist,
    FileOperationError,
    FileRequestError,
    InvalidPage,
    ValidationError,
    ContractValidationError,
    DatabaseError,
    ImproperlyConfigured,
    OSError,
)


def build_file_error_response(e: Exception) -> JsonResponse:
    if isinstance(e, (SessionInvalidatedError, InvalidApiKeyError)):
        response = build_error_response(
            "api_key_authentication_required"
            if isinstance(e, InvalidApiKeyError)
            else "authentication_required",
            "Valid credentials are required.",
            statusCode=401,
        )
        if isinstance(e, InvalidApiKeyError):
            response["WWW-Authenticate"] = (
                'Bearer realm="LiberRPA Console", error="invalid_token"'
            )
        return response
    if isinstance(e, PermissionDenied):
        return build_error_response(
            "file_access_required", "Shared file access is unavailable.", statusCode=403
        )
    if isinstance(
        e,
        (
            SharedFile.DoesNotExist,
            Department.DoesNotExist,
            UploadSession.DoesNotExist,
            DownloadSession.DoesNotExist,
        ),
    ):
        return build_error_response(
            "file_not_found",
            "The file, department, or transfer is unavailable.",
            statusCode=404,
        )
    if isinstance(e, FileOperationError):
        response = build_error_response(e.code, str(e), statusCode=e.status)
        if e.status in (429, 503):
            response["Retry-After"] = "5"
        return response
    if isinstance(e, FileRequestError):
        return build_error_response("invalid_request", str(e), statusCode=400)
    if isinstance(e, InvalidPage):
        return build_error_response(
            "invalid_page", "The requested page is unavailable.", statusCode=400
        )
    if isinstance(e, ValidationError):
        return build_error_response(
            "invalid_file_path", " ".join(e.messages), statusCode=400
        )
    if isinstance(e, ContractValidationError):
        _LOGGER.exception("Invalid shared file response or receipt contract.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )
    return build_service_unavailable_response()


def session_file_view[**P](
    view: Callable[Concatenate[HttpRequest, FileAuthentication, P], HttpResponseBase],
) -> Callable[Concatenate[HttpRequest, P], HttpResponseBase]:
    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(
        request: HttpRequest, *args: P.args, **kwargs: P.kwargs
    ) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        try:
            membership = get_current_membership(actorId=cast(User, request.user).id)
            return view(request, membership, *args, **kwargs)
        except _HANDLED_ERRORS as e:
            return build_file_error_response(e)

    return wrapped


def api_file_view[**P](
    view: Callable[Concatenate[HttpRequest, FileAuthentication, P], HttpResponseBase],
) -> Callable[Concatenate[HttpRequest, P], HttpResponseBase]:
    """Public routes authenticate only the Bearer key, including binary downloads."""

    @csrf_exempt
    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(
        request: HttpRequest, *args: P.args, **kwargs: P.kwargs
    ) -> HttpResponseBase:
        try:
            retryAfter = apply_api_key_authentication_rate_limit(
                request.META.get("REMOTE_ADDR", "")
            )
            if retryAfter:
                return build_rate_limited_response(retryAfter)
            authentication = authenticate_api_key(
                request.headers.get("Authorization", "")
            )
            return view(request, authentication, *args, **kwargs)
        except _HANDLED_ERRORS as e:
            return build_file_error_response(e)

    return wrapped


def get_file_access(authentication: FileAuthentication) -> OrganizationAccessContext:
    if isinstance(authentication, ApiKeyAuthenticationContext):
        return authentication.access
    return resolve_organization_access(
        actorId=authentication.user_id,
        organizationId=authentication.organization_id,
        channel=AccessChannel.SESSION,
    )


def lock_file_access(
    request: HttpRequest, authentication: FileAuthentication
) -> OrganizationAccessContext:
    if isinstance(authentication, ApiKeyAuthenticationContext):
        return lock_api_key_write_access(authentication)
    return lock_session_write_access(
        authentication.user_id,
        authentication.organization_id,
        AccessChannel.SESSION,
        request.session.get(HASH_SESSION_KEY, ""),
        request.session.get_expiry_date(),
    )


def require_no_query_parameters(request: HttpRequest) -> None:
    if request.GET:
        raise FileRequestError("Use the request body; query parameters are not accepted.")


def parse_file_request[Payload: JsonRequest](
    request: HttpRequest, requestSchema: type[Payload]
) -> Payload | JsonResponse:
    require_no_query_parameters(request)
    return parse_json_request(
        request, requestSchema, maxBodyBytes=MAX_FILE_RESPONSE_BYTES
    )


def parse_file_path(value: str, *, departmentOnly: bool = False) -> tuple[str, ...]:
    """Normalize and validate once at the HTTP boundary, before taking business locks."""
    value = value.replace("\\", "/")
    if departmentOnly:
        value = value.removesuffix("/")
    parts = value.removeprefix("/").split("/")
    if len(parts) < (1 if departmentOnly else 2) or len(parts) > 65:
        raise ValidationError("Use a full department path and file name.")
    return tuple(normalize_path_name(part) for part in parts)


def parse_upload_chunk(request: HttpRequest) -> tuple[bytes, str]:
    require_no_query_parameters(request)
    if request.content_type != "application/octet-stream":
        raise FileOperationError(
            "invalid_chunk_type", "Send application/octet-stream content.", 415
        )
    data = request.read(UPLOAD_CHUNK_BYTES + 1)
    if not data or len(data) > UPLOAD_CHUNK_BYTES:
        raise FileOperationError(
            "invalid_chunk_size", "Send a non-empty chunk of at most 4 MiB.", 400
        )
    chunkSha256 = hashlib.sha256(data).hexdigest()
    if chunkSha256 != request.headers.get("X-Chunk-SHA256", ""):
        raise FileOperationError(
            "chunk_checksum_mismatch",
            "The chunk checksum does not match its content.",
            400,
        )
    return data, chunkSha256


def build_file_response(
    payload: JsonResponsePayload, *, statusCode: int = 200
) -> HttpResponse:
    content = payload.model_dump_json().encode("utf-8")
    if len(content) > MAX_FILE_RESPONSE_BYTES:
        raise FileOperationError(
            "file_response_too_large", "The response exceeds the byte limit."
        )
    return HttpResponse(content, status=statusCode, content_type="application/json")
