# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import transaction
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from console_project.http import parse_json_request, parse_page_number
from console_project.contracts import JsonRequest
from file_storage.http import (
    FileAuthentication,
    get_file_access,
    lock_file_access,
    require_no_query_parameters,
    parse_upload_chunk,
)
from file_storage.proxy import get_download_proxy_snapshot
from file_storage.services import FileOperationError, release_unstarted_download
from file_storage.streaming import SyncFileStream, AsyncFileStream
from organizations.access_info import get_department_access_info
from organizations.http import parse_department_resource_filters
from organizations.contracts import DepartmentRole
from organizations.permissions import OrganizationAccessContext
from organizations.rate_limits import RequestBudget, request_budget

from .contracts import (
    EmptyRequest,
    PackageUploadRequest,
    PackageSettingsRequest,
    PackageUploadState,
    RunSettings,
)
from .models import Package
from .queries import (
    get_package_query,
    build_package_payload,
    get_package_project_groups,
    get_project_packages,
    get_package_options,
    get_upload,
    build_upload_payload,
)
from .services import (
    create_upload,
    append_chunk,
    validate_upload_content,
    complete_upload,
    cancel_upload,
    save_package_settings,
    prepare_download,
    open_download,
    get_package_references,
    delete_package,
)
from .http import build_package_error


def _parse_request[Payload: JsonRequest](
    request: HttpRequest, schema: type[Payload]
) -> Payload | JsonResponse:
    require_no_query_parameters(request)
    return parse_json_request(request, schema, maxBodyBytes=2 * 1024 * 1024)


@require_GET
def list_departments(
    request: HttpRequest, authentication: FileAuthentication
) -> JsonResponse:
    require_no_query_parameters(request)
    access = get_file_access(authentication)
    return JsonResponse({
        "departments": [
            {"id": str(department.id), "name": department.name, "path": department.path}
            for department in get_department_access_info(access)
            if access.isOrgAdmin or department.role == DepartmentRole.DEVELOPER
        ]
    })


@require_GET
def list_package_project_groups(
    request: HttpRequest, authentication: FileAuthentication
) -> JsonResponse:
    if set(request.GET) - {"department_id", "page", "locate_package_id"}:
        raise ValueError("Unknown project group filters.")
    if len(request.GET.getlist("locate_package_id")) > 1:
        raise ValueError("Select one package to locate.")
    filters = parse_department_resource_filters(
        request.GET, extraFields=frozenset({"locate_package_id"})
    )
    locatePackageId = (
        uuid.UUID(request.GET["locate_package_id"])
        if "locate_package_id" in request.GET
        else None
    )
    return JsonResponse(
        get_package_project_groups(
            get_file_access(authentication),
            pageNumber=filters["pageNumber"],
            departmentIds=filters["departmentIds"],
            locatePackageId=locatePackageId,
        )
    )


@require_GET
def list_project_packages(
    request: HttpRequest, authentication: FileAuthentication, packageId: uuid.UUID
) -> JsonResponse:
    if set(request.GET) - {"page"}:
        raise ValueError("Unknown project package filters.")
    return JsonResponse(
        get_project_packages(
            get_file_access(authentication),
            packageId,
            pageNumber=parse_page_number(request.GET) if "page" in request.GET else None,
        )
    )


@require_GET
def package_options(
    request: HttpRequest, authentication: FileAuthentication
) -> JsonResponse:
    if (
        set(request.GET) != {"department_id"}
        or len(request.GET.getlist("department_id")) != 1
    ):
        raise ValueError("Select one department.")
    departmentId = uuid.UUID(request.GET["department_id"])
    return JsonResponse(
        get_package_options(get_file_access(authentication), departmentId)
    )


def _build_package_details_response(
    package: Package,
    access: OrganizationAccessContext,
    *,
    runSettings: RunSettings | None = None,
) -> JsonResponse:
    from .preparation import get_package_preparation

    return JsonResponse({
        "package": build_package_payload(package, access, runSettings=runSettings),
        "preparation": get_package_preparation(package),
        "references": get_package_references(package),
    })


@require_GET
def package_detail(
    request: HttpRequest, authentication: FileAuthentication, packageId: uuid.UUID
) -> JsonResponse:
    require_no_query_parameters(request)
    access = get_file_access(authentication)
    package = get_package_query(access).get(pk=packageId)
    return _build_package_details_response(package, access)


@require_POST
def update_settings(
    request: HttpRequest, authentication: FileAuthentication, packageId: uuid.UUID
) -> JsonResponse:
    payload = _parse_request(request, PackageSettingsRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        package = get_package_query(access, manage=True).get(pk=packageId)
        save_package_settings(access, package, payload)
        return _build_package_details_response(
            package, access, runSettings=payload.settings
        )


@require_POST
@request_budget(RequestBudget.INDEPENDENT)
def cancel_preparation(
    request: HttpRequest, authentication: FileAuthentication, packageId: uuid.UUID
) -> JsonResponse:
    from .preparation import cancel_package_preparation

    payload = _parse_request(request, EmptyRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        package = get_package_query(access, manage=True).get(pk=packageId)
        intCanceledCount = cancel_package_preparation(access, package)
    return JsonResponse({"canceled_count": intCanceledCount})


@require_POST
def remove_package(
    request: HttpRequest, authentication: FileAuthentication, packageId: uuid.UUID
) -> JsonResponse:
    payload = _parse_request(request, EmptyRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        delete_package(access, get_package_query(access, manage=True).get(pk=packageId))
    return JsonResponse({"message": "Package deleted."})


@require_POST
def start_upload(
    request: HttpRequest, authentication: FileAuthentication
) -> JsonResponse:
    payload = _parse_request(request, PackageUploadRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        return JsonResponse(
            build_upload_payload(create_upload(access, payload)), status=201
        )


@require_GET
def upload_detail(
    request: HttpRequest, authentication: FileAuthentication, uploadId: uuid.UUID
) -> JsonResponse:
    require_no_query_parameters(request)
    return JsonResponse(
        build_upload_payload(get_upload(get_file_access(authentication), uploadId))
    )


@require_http_methods(["PUT"])
@request_budget(RequestBudget.INDEPENDENT)
def upload_chunk(
    request: HttpRequest,
    authentication: FileAuthentication,
    uploadId: uuid.UUID,
    offset: int,
) -> JsonResponse:
    chunkData, strChunkSha256 = parse_upload_chunk(request)
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        upload = get_upload(access, uploadId)
        append_chunk(upload, offset, chunkData, strChunkSha256)
        return JsonResponse(build_upload_payload(upload))


@require_POST
@request_budget(RequestBudget.INDEPENDENT)
def finish_upload(
    request: HttpRequest, authentication: FileAuthentication, uploadId: uuid.UUID
) -> JsonResponse:
    payload = _parse_request(request, EmptyRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        upload = get_upload(access, uploadId)
        if upload.state == PackageUploadState.COMPLETED:
            return JsonResponse(build_upload_payload(upload))
    # The file scan must not hold the organization lock or a database transaction.
    validationResult = validate_upload_content(upload)
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        result = complete_upload(access, get_upload(access, uploadId), validationResult)
    return (
        build_package_error(result)
        if isinstance(result, FileOperationError)
        else JsonResponse(result)
    )


@require_POST
@request_budget(RequestBudget.INDEPENDENT)
def abort_upload(
    request: HttpRequest, authentication: FileAuthentication, uploadId: uuid.UUID
) -> JsonResponse:
    payload = _parse_request(request, EmptyRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        upload = get_upload(access, uploadId)
        cancel_upload(upload)
        return JsonResponse(build_upload_payload(upload))


@require_POST
@request_budget(RequestBudget.READ)
def start_download(
    request: HttpRequest, authentication: FileAuthentication, packageId: uuid.UUID
) -> JsonResponse:
    payload = _parse_request(request, EmptyRequest)
    if isinstance(payload, JsonResponse):
        return payload
    proxySnapshot = get_download_proxy_snapshot()
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        return JsonResponse(
            prepare_download(
                access, get_package_query(access).get(pk=packageId), proxySnapshot
            ),
            status=201,
        )


@require_GET
@request_budget(RequestBudget.INDEPENDENT)
def download_content(
    request: HttpRequest, authentication: FileAuthentication, transferId: uuid.UUID
) -> StreamingHttpResponse:
    require_no_query_parameters(request)
    if "Range" in request.headers:
        raise FileOperationError(
            "range_not_supported", "Start a new complete Package download.", 416
        )
    access = None
    stream = None
    try:
        with transaction.atomic():
            access = lock_file_access(request, authentication)
            transfer, handle = open_download(access, transferId)
            stream = (AsyncFileStream if hasattr(request, "scope") else SyncFileStream)(
                transfer, handle
            )
            response = StreamingHttpResponse(stream, content_type="application/zip")
            response["Content-Disposition"] = content_disposition_header(
                True, transfer.name
            )
            response["Content-Length"] = str(transfer.blob.size_bytes)
            response["ETag"] = f'"{transfer.blob.sha256}"'
            response["X-Content-Type-Options"] = "nosniff"
            response["Accept-Ranges"] = "none"
        return response
    except Exception:
        if stream is not None:
            stream.close()
        elif access is not None:
            release_unstarted_download(transferId, access.organization.pk, access.actorId)
        raise


@require_POST
@request_budget(RequestBudget.INDEPENDENT)
def preparation_result(
    request: HttpRequest, authentication: FileAuthentication, preparationId: uuid.UUID
) -> JsonResponse:
    from accounts.resource_authentication import NativeResourceAuthenticationContext
    from .contracts import PreparationResultRequest
    from .preparation import complete_preparation

    payload = _parse_request(request, PreparationResultRequest)
    if isinstance(payload, JsonResponse):
        return payload
    if not isinstance(authentication, NativeResourceAuthenticationContext):
        raise FileOperationError(
            "executor_session_required", "An Executor session is required.", 403
        )
    with transaction.atomic():
        access = lock_file_access(request, authentication)
        complete_preparation(
            access, authentication, preparationId, payload.state, payload.reason
        )
    return JsonResponse({"message": "Package preparation report received."})
