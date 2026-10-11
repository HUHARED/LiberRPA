# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
from collections.abc import Callable
from functools import wraps
from typing import Concatenate

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from pydantic import ValidationError as ContractValidationError

from accounts.api_key_authentication import InvalidApiKeyError
from accounts.resource_authentication import (
    InvalidResourceCredentialError,
    build_resource_authentication_required_response,
    authenticate_resource_request,
)
from accounts.session_revocation import SessionInvalidatedError
from console_project.contracts import JsonRequest, JsonResponsePayload
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
)
from file_storage.http import (
    FileAuthentication,
    FileRequestError,
    require_no_query_parameters,
)
from file_storage.models import DownloadSession
from file_storage.services import FileOperationError
from organizations.http import get_request_membership
from organizations.models import Department

from .contracts import MAX_FILE_RESPONSE_BYTES
from .models import SharedFile, UploadSession

_LOGGER = logging.getLogger("console.shared_files")

_HANDLED_ERRORS = (
    PermissionDenied,
    InvalidApiKeyError,
    InvalidResourceCredentialError,
    SessionInvalidatedError,
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
    if isinstance(e, (InvalidApiKeyError, InvalidResourceCredentialError)):
        return build_resource_authentication_required_response()
    if isinstance(e, SessionInvalidatedError):
        return build_authentication_required_response()
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
        try:
            membership = get_request_membership(request)
            if isinstance(membership, JsonResponse):
                return membership
            return view(request, membership, *args, **kwargs)
        except _HANDLED_ERRORS as e:
            return build_file_error_response(e)

    return wrapped


def api_file_view[**P](
    view: Callable[Concatenate[HttpRequest, FileAuthentication, P], HttpResponseBase],
) -> Callable[Concatenate[HttpRequest, P], HttpResponseBase]:
    """Authenticate the Bearer key or native session, including binary downloads."""

    @csrf_exempt
    @never_cache
    @sensitive_variables()
    @wraps(view)
    def wrapped(
        request: HttpRequest, *args: P.args, **kwargs: P.kwargs
    ) -> HttpResponseBase:
        try:
            authentication = authenticate_resource_request(request)
            if isinstance(authentication, JsonResponse):
                return authentication
            return view(request, authentication, *args, **kwargs)
        except _HANDLED_ERRORS as e:
            return build_file_error_response(e)

    return wrapped


def parse_file_request[Payload: JsonRequest](
    request: HttpRequest, requestSchema: type[Payload]
) -> Payload | JsonResponse:
    require_no_query_parameters(request)
    return parse_json_request(
        request, requestSchema, maxBodyBytes=MAX_FILE_RESPONSE_BYTES
    )


def build_file_response(
    payload: JsonResponsePayload, *, statusCode: int = 200
) -> HttpResponse:
    content = payload.model_dump_json().encode("utf-8")
    if len(content) > MAX_FILE_RESPONSE_BYTES:
        raise FileOperationError(
            "file_response_too_large", "The response exceeds the byte limit."
        )
    return HttpResponse(content, status=statusCode, content_type="application/json")
