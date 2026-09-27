# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_http_methods, require_GET, require_POST

from file_storage.services import FileOperationError
from file_storage.streaming import SyncFileStream, AsyncFileStream

from .contracts import (
    FileListRequest,
    FilePathRequest,
    FileUploadRequest,
    FileDeleteRequest,
    EmptyFileRequest,
)
from .queries import (
    build_file_payload,
    resolve_file,
    get_file_list,
    build_upload_payload,
    get_upload,
)
from .services import (
    create_upload,
    append_chunk,
    cancel_upload,
    complete_upload,
    delete_files,
    prepare_download,
    open_download,
)
from .http import (
    FileAuthentication,
    build_file_error_response,
    get_file_access,
    lock_file_access,
    require_no_query_parameters,
    parse_file_request,
    parse_file_path,
    parse_upload_chunk,
    build_file_response,
)


@require_POST
def list_shared_files(
    request: HttpRequest, authentication: FileAuthentication
) -> HttpResponse:
    payload = parse_file_request(request, FileListRequest)
    if isinstance(payload, JsonResponse):
        return payload
    departmentParts = parse_file_path(payload.department_path, departmentOnly=True)
    access = get_file_access(authentication)
    return build_file_response(get_file_list(access, payload, departmentParts))


@require_POST
def query_shared_file(
    request: HttpRequest, authentication: FileAuthentication
) -> HttpResponse:
    payload = parse_file_request(request, FilePathRequest)
    if isinstance(payload, JsonResponse):
        return payload
    pathParts = parse_file_path(payload.path)
    file, departmentPath = resolve_file(get_file_access(authentication), pathParts)
    return build_file_response(build_file_payload(file, departmentPath))


@require_POST
def create_file_upload(
    request: HttpRequest, authentication: FileAuthentication
) -> HttpResponse:
    payload = parse_file_request(request, FileUploadRequest)
    if isinstance(payload, JsonResponse):
        return payload
    pathParts = parse_file_path(payload.path)
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        upload = create_upload(access, payload, pathParts)
        return build_file_response(build_upload_payload(upload), statusCode=201)


@require_GET
def get_file_upload(
    request: HttpRequest, authentication: FileAuthentication, uploadId: uuid.UUID
) -> HttpResponse:
    require_no_query_parameters(request)
    upload = get_upload(get_file_access(authentication), uploadId)
    return build_file_response(build_upload_payload(upload))


@require_http_methods(["PUT"])
def append_file_chunk(
    request: HttpRequest,
    authentication: FileAuthentication,
    uploadId: uuid.UUID,
    offset: int,
) -> HttpResponse:
    data, chunkSha256 = parse_upload_chunk(request)
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        upload = get_upload(access, uploadId)
        append_chunk(upload, offset, data, chunkSha256)
        return build_file_response(build_upload_payload(upload))


@require_POST
def complete_file_upload(
    request: HttpRequest, authentication: FileAuthentication, uploadId: uuid.UUID
) -> HttpResponse:
    payload = parse_file_request(request, EmptyFileRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        result = complete_upload(access, get_upload(access, uploadId))
        if isinstance(result, FileOperationError):
            return build_file_error_response(result)
        return build_file_response(result)


@require_POST
def cancel_file_upload(
    request: HttpRequest, authentication: FileAuthentication, uploadId: uuid.UUID
) -> HttpResponse:
    payload = parse_file_request(request, EmptyFileRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        upload = cancel_upload(get_upload(access, uploadId))
        return build_file_response(build_upload_payload(upload))


@require_POST
def delete_shared_files(
    request: HttpRequest, authentication: FileAuthentication
) -> HttpResponse:
    payload = parse_file_request(request, FileDeleteRequest)
    if isinstance(payload, JsonResponse):
        return payload
    paths = [parse_file_path(path) for path in payload.paths]
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        return build_file_response(delete_files(access, payload, paths))


@require_POST
def create_file_download(
    request: HttpRequest, authentication: FileAuthentication
) -> HttpResponse:
    payload = parse_file_request(request, FilePathRequest)
    if isinstance(payload, JsonResponse):
        return payload
    pathParts = parse_file_path(payload.path)
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        return build_file_response(prepare_download(access, pathParts), statusCode=201)


@require_GET
def download_file_content(
    request: HttpRequest, authentication: FileAuthentication, transferId: uuid.UUID
) -> StreamingHttpResponse:
    require_no_query_parameters(request)
    if "Range" in request.headers:
        raise FileOperationError(
            "range_not_supported",
            "Start a new complete download; range requests are not supported.",
            416,
        )
    stream = None
    try:
        with transaction.atomic():
            access = lock_file_access(request, authentication)
            transfer, handle = open_download(access, transferId)
            stream = (AsyncFileStream if hasattr(request, "scope") else SyncFileStream)(
                transfer, handle
            )
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
        # The transaction commits before Django starts iterating over the file.
        return response
    except Exception:
        if stream is not None:
            stream.close()
        raise
