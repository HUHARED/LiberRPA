# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from typing import cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, transaction
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    HttpResponseNotAllowed,
    JsonResponse,
    StreamingHttpResponse,
)
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from pydantic import BaseModel

from accounts.api_key_authentication import (
    InvalidApiKeyError,
    authenticate_api_key,
    lock_api_key_write_access,
)
from accounts.models import User
from accounts.rate_limits import reserve_api_key_authentication_request
from accounts.session_revocation import SessionInvalidatedError, lock_session_write_access
from console_project.http import (
    build_error_response,
    build_rate_limited_response,
    build_service_unavailable_response,
    parse_json_request,
)
from file_storage.models import DownloadSession
from file_storage.services import CHUNK_BYTES, FileOperationError
from file_storage.streaming import AsyncFileStream, SyncFileStream
from organizations.models import Department
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
)

from .contracts import (
    EmptyFileRequest,
    FileDeleteRequest,
    FileDeleteResponse,
    FileDownloadResponse,
    FileInfoResponse,
    FileListRequest,
    FileListResponse,
    FilePathRequest,
    FileUploadRequest,
    FileUploadResponse,
)
from .models import SharedFile, UploadSession
from .services import (
    append_chunk,
    cancel_upload,
    complete_upload,
    create_upload,
    delete_files,
    file_info,
    get_upload,
    list_files,
    open_download,
    prepare_download,
    resolve_file,
    upload_info,
)

MAX_JSON_BYTES = 2 * 1024 * 1024
_SCHEMAS = {
    "list": FileListRequest,
    "query": FilePathRequest,
    "upload": FileUploadRequest,
    "delete": FileDeleteRequest,
    "download": FilePathRequest,
    "complete": EmptyFileRequest,
    "cancel": EmptyFileRequest,
}


def _response(
    model: type[BaseModel], payload: dict[str, object], status: int = 200
) -> HttpResponse:
    serialized = json.dumps(
        payload, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":")
    )
    content = model.model_validate_json(serialized).model_dump_json().encode("utf-8")
    if len(content) > MAX_JSON_BYTES:
        raise FileOperationError(
            "file_response_too_large", "The response exceeds the byte limit."
        )
    return HttpResponse(content, status=status, content_type="application/json")


def _error(error: Exception) -> JsonResponse:
    if isinstance(error, (SessionInvalidatedError, InvalidApiKeyError)):
        response = build_error_response(
            "api_key_authentication_required"
            if isinstance(error, InvalidApiKeyError)
            else "authentication_required",
            "Valid credentials are required.",
            statusCode=401,
        )
        if isinstance(error, InvalidApiKeyError):
            response["WWW-Authenticate"] = (
                'Bearer realm="LiberRPA Console", error="invalid_token"'
            )
        return response
    if isinstance(error, PermissionDenied):
        return build_error_response(
            "file_access_required", "Shared file access is unavailable.", statusCode=403
        )
    if isinstance(
        error,
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
    if isinstance(error, FileOperationError):
        response = build_error_response(error.code, str(error), statusCode=error.status)
        if error.status in (429, 503):
            response["Retry-After"] = "5"
        return response
    if isinstance(error, InvalidPage):
        return build_error_response(
            "invalid_page", "The requested page is unavailable.", statusCode=400
        )
    if isinstance(error, ValidationError):
        return build_error_response(
            "invalid_file_path", " ".join(error.messages), statusCode=400
        )
    if isinstance(error, ValueError):
        return build_error_response(
            "invalid_request",
            "Use the supported request fields and filters.",
            statusCode=400,
        )
    return build_service_unavailable_response()


_HANDLED_ERRORS = (
    SessionInvalidatedError,
    InvalidApiKeyError,
    PermissionDenied,
    SharedFile.DoesNotExist,
    Department.DoesNotExist,
    UploadSession.DoesNotExist,
    DownloadSession.DoesNotExist,
    FileOperationError,
    InvalidPage,
    ValidationError,
    ValueError,
    DatabaseError,
    ImproperlyConfigured,
    OSError,
)


def _dispatch(
    request: HttpRequest,
    access: OrganizationAccessContext,
    action: str,
    transferId: uuid.UUID | None,
    offset: int | None,
) -> HttpResponseBase:
    if request.GET:
        raise ValueError("Use the request body; query parameters are not accepted.")
    if action == "content":
        assert transferId is not None
        if "Range" in request.headers:
            raise FileOperationError(
                "range_not_supported",
                "Start a new complete download; range requests are not supported.",
                416,
            )
        transfer, handle = open_download(access, transferId)
        stream = (AsyncFileStream if hasattr(request, "scope") else SyncFileStream)(
            transfer, handle
        )
        try:
            response = StreamingHttpResponse(
                stream, content_type="application/octet-stream"
            )
            response["Content-Disposition"] = content_disposition_header(
                True, transfer.name
            )
            response["Content-Length"] = str(transfer.blob.size_bytes)
            response["ETag"] = f'"{transfer.blob.sha256}"'
            response["X-Content-Type-Options"] = "nosniff"
            response["Accept-Ranges"] = "none"
            return response
        except Exception:
            stream.close()
            raise
    upload = None
    if action in ("status", "chunk", "complete", "cancel"):
        assert transferId is not None
        upload = get_upload(access, transferId)
        if action == "status":
            return _response(FileUploadResponse, upload_info(upload))
        if action == "chunk":
            assert offset is not None
            if request.content_type != "application/octet-stream":
                raise FileOperationError(
                    "invalid_chunk_type", "Send application/octet-stream content.", 415
                )
            data = request.read(CHUNK_BYTES + 1)
            upload = append_chunk(
                upload, offset, data, request.headers.get("X-Chunk-SHA256", "")
            )
            return _response(FileUploadResponse, upload_info(upload))
    payload = parse_json_request(request, _SCHEMAS[action], maxBodyBytes=MAX_JSON_BYTES)
    if isinstance(payload, JsonResponse):
        return payload
    if action == "list":
        assert isinstance(payload, FileListRequest)
        return _response(FileListResponse, list_files(access, payload))
    if action == "query":
        assert isinstance(payload, FilePathRequest)
        return _response(FileInfoResponse, file_info(resolve_file(access, payload.path)))
    if action == "upload":
        assert isinstance(payload, FileUploadRequest)
        return _response(
            FileUploadResponse, upload_info(create_upload(access, payload)), 201
        )
    if action == "delete":
        assert isinstance(payload, FileDeleteRequest)
        return _response(FileDeleteResponse, delete_files(access, payload))
    if action == "download":
        assert isinstance(payload, FilePathRequest)
        return _response(
            FileDownloadResponse, prepare_download(access, payload.path), 201
        )
    assert upload is not None
    if action == "cancel":
        return _response(FileUploadResponse, upload_info(cancel_upload(upload)))
    result = complete_upload(access, upload)
    if isinstance(result, FileOperationError):
        return _error(result)
    return _response(FileUploadResponse, upload_info(result))


@sensitive_variables()
def _request(
    request: HttpRequest,
    *,
    action: str,
    public: bool,
    transferId: uuid.UUID | None = None,
    offset: int | None = None,
) -> HttpResponseBase:
    method = (
        "GET"
        if action in ("status", "content")
        else "PUT"
        if action == "chunk"
        else "POST"
    )
    if request.method != method:
        return HttpResponseNotAllowed([method])
    response = None
    try:
        if public:
            retryAfter = reserve_api_key_authentication_request(
                request.META.get("REMOTE_ADDR", "")
            )
            if retryAfter:
                return build_rate_limited_response(retryAfter)
            authentication = authenticate_api_key(
                request.headers.get("Authorization", "")
            )
        else:
            if not request.user.is_authenticated:
                return build_error_response(
                    "authentication_required", "Sign in to continue.", statusCode=401
                )
            membership = get_current_membership(actorId=cast(User, request.user).id)
        with transaction.atomic():
            access = (
                lock_api_key_write_access(authentication)
                if public
                else lock_session_write_access(
                    membership.user_id,
                    membership.organization_id,
                    AccessChannel.SESSION,
                    request.session.get(HASH_SESSION_KEY, ""),
                    request.session.get_expiry_date(),
                )
            )
            response = _dispatch(request, access, action, transferId, offset)
        return response
    except _HANDLED_ERRORS as error:
        if isinstance(response, StreamingHttpResponse):
            response.close()
        return _error(error)


@never_cache
def file_request(request: HttpRequest, **kwargs) -> HttpResponseBase:
    return _request(request, public=False, **kwargs)


@csrf_exempt
@never_cache
def public_file_request(request: HttpRequest, **kwargs) -> HttpResponseBase:
    """Public requests are Bearer-only, including protected binary downloads."""
    return _request(request, public=True, **kwargs)
