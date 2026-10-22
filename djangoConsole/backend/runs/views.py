# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Concatenate

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponseBase, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.api_key_authentication import (
    ApiKeyAuthenticationContext,
    InvalidApiKeyError,
)
from accounts.resource_authentication import (
    authenticate_resource_request,
    lock_resource_write_access,
)
from accounts.session_revocation import SessionInvalidatedError
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
)
from organizations.http import get_request_membership, lock_request_write_access
from organizations.models import Membership
from organizations.rate_limits import RequestBudget, check_request_budget, request_budget
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    build_organization_access,
)
from organizations.validators import get_path_name_key
from operations.contracts import AuditAction
from operations.audit import record_audit
from operations.maintenance import ServiceMaintenanceError
from packages.models import Package

from .contracts import (
    JobState,
    RunStatus,
    JobControlAction,
    JobCreationRequest,
    JobControlRequest,
    EmptyRequest,
)
from .queries import (
    get_visible_jobs,
    get_visible_runs,
    get_history_departments,
    build_job_payload,
    build_job_payloads,
    build_run_payload,
    get_matching_run_ids,
    list_work,
)
from .overview import list_current_runs, get_run_statistics
from .admission import accept_request
from .services import control_job

_LOGGER = logging.getLogger("console.runs")
type WorkAuthentication = ApiKeyAuthenticationContext | Membership


def _build_error(e: Exception) -> JsonResponse:
    if isinstance(e, (SessionInvalidatedError, InvalidApiKeyError)):
        return build_error_response(
            "authentication_required", "Sign in again.", statusCode=401
        )
    if isinstance(e, PermissionDenied):
        return build_error_response("run_access_required", str(e), statusCode=403)
    if isinstance(e, ObjectDoesNotExist):
        return build_error_response(
            "work_not_found", "This work or resource is unavailable.", statusCode=404
        )
    if isinstance(e, (ValidationError, ValueError, InvalidPage)):
        return build_error_response(
            getattr(e, "code", None) or "invalid_run_request",
            "; ".join(e.messages) if isinstance(e, ValidationError) else str(e),
            statusCode=503 if isinstance(e, ServiceMaintenanceError) else 400,
            fields=e.message_dict
            if isinstance(e, ValidationError) and hasattr(e, "message_dict")
            else None,
        )
    _LOGGER.exception("Run request failed.")
    return build_service_unavailable_response()


def _get_authentication(
    request: HttpRequest,
) -> WorkAuthentication | JsonResponse:
    if request.headers.get("Authorization"):
        authentication = authenticate_resource_request(request)
        if isinstance(authentication, JsonResponse):
            return authentication
        if not isinstance(authentication, ApiKeyAuthenticationContext):
            raise PermissionDenied("This endpoint requires a web session or API key.")
        return authentication
    return get_request_membership(request)


def _get_access(
    request: HttpRequest,
    authentication: WorkAuthentication,
    *,
    write: bool,
) -> OrganizationAccessContext:
    if isinstance(authentication, ApiKeyAuthenticationContext):
        return (
            lock_resource_write_access(authentication) if write else authentication.access
        )
    if write:
        return lock_request_write_access(request, authentication)
    return build_organization_access(authentication, channel=AccessChannel.SESSION)


def _work_view[**P](
    view: Callable[Concatenate[HttpRequest, WorkAuthentication, P], HttpResponseBase],
) -> Callable[Concatenate[HttpRequest, P], HttpResponseBase]:
    def process_request(
        request: HttpRequest,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> HttpResponseBase:
        try:
            authentication = _get_authentication(request)
            if isinstance(authentication, JsonResponse):
                return authentication
            return view(request, authentication, *args, **kwargs)
        except (
            PermissionDenied,
            ValidationError,
            ValueError,
            ObjectDoesNotExist,
            InvalidPage,
            DatabaseError,
            SessionInvalidatedError,
            InvalidApiKeyError,
        ) as e:
            return _build_error(e)

    # API keys authenticate independently; cookie-authenticated writes still require CSRF.
    protected = csrf_protect(process_request)

    @csrf_exempt
    @never_cache
    @wraps(view)
    def wrapped(
        request: HttpRequest,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> HttpResponseBase:
        if request.headers.get("Authorization"):
            return process_request(request, *args, **kwargs)
        return protected(request, *args, **kwargs)

    return wrapped


@_work_view
@require_http_methods(["GET", "POST"])
@request_budget(RequestBudget.DEFERRED, methods=("POST",))
def list_or_create_jobs(
    request: HttpRequest,
    authentication: WorkAuthentication,
) -> JsonResponse:
    if request.method == "GET":
        access = _get_access(request, authentication, write=False)
        return JsonResponse(list_work(access, request.GET, runs=False))
    payload = parse_json_request(
        request, JobCreationRequest, maxBodyBytes=2 * 1024 * 1024
    )
    if isinstance(payload, JsonResponse):
        return payload
    organization = (
        authentication.access.organization
        if isinstance(authentication, ApiKeyAuthenticationContext)
        else authentication.organization
    )
    check_request_budget(
        request,
        organization,
        budget=RequestBudget.WRITE,
        cost=len(payload.executor_ids) if payload.executor_ids else 1,
    )
    with transaction.atomic():
        access = _get_access(request, authentication, write=True)
        jobRequest, boolCreated = accept_request(access, payload)
        return JsonResponse(
            {
                "request_id": jobRequest.client_request_id,
                "job_request_id": jobRequest.id,
                "jobs": build_job_payloads(jobRequest.jobs.select_related("request")),
            },
            status=201 if boolCreated else 200,
        )


@_work_view
@require_GET
def job_detail(
    request: HttpRequest,
    authentication: WorkAuthentication,
    workId: uuid.UUID,
) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    return JsonResponse({
        "job": build_job_payload(get_visible_jobs(access).get(pk=workId), details=True)
    })


@_work_view
@require_POST
@request_budget(RequestBudget.CONTROL)
def update_job(
    request: HttpRequest,
    authentication: WorkAuthentication,
    workId: uuid.UUID,
) -> JsonResponse:
    payload = parse_json_request(request, JobControlRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = _get_access(request, authentication, write=True)
        job = get_visible_jobs(access).select_for_update(of=("self",)).get(pk=workId)
        strPreviousState = job.state
        if control_job(job, payload.action):
            record_audit(
                {
                    JobControlAction.CANCEL: AuditAction.JOB_CANCEL,
                    JobControlAction.STOP: AuditAction.JOB_STOP,
                    JobControlAction.CLOSE: AuditAction.JOB_CLOSE,
                }[payload.action],
                actor=access.actor,
                organization=access.organization,
                target=job,
                channel=access.channel,
                metadata={"previous_state": strPreviousState, "state": job.state},
            )
        return JsonResponse({"job": build_job_payload(job, details=True)})


@_work_view
@require_GET
def list_runs(request: HttpRequest, authentication: WorkAuthentication) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    return JsonResponse(list_work(access, request.GET, runs=True))


@_work_view
@require_GET
def current_runs(
    request: HttpRequest, authentication: WorkAuthentication
) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    return JsonResponse(list_current_runs(access, request.GET))


@_work_view
@require_GET
def run_statistics(
    request: HttpRequest, authentication: WorkAuthentication
) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    return JsonResponse(get_run_statistics(access, request.GET))


@_work_view
@require_GET
def run_selection(
    request: HttpRequest,
    authentication: WorkAuthentication,
) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    return JsonResponse({"run_ids": get_matching_run_ids(access, request.GET)})


@_work_view
@require_GET
def history_departments(
    request: HttpRequest,
    authentication: WorkAuthentication,
) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    return JsonResponse({"departments": get_history_departments(access)})


@_work_view
@require_GET
def run_detail(
    request: HttpRequest,
    authentication: WorkAuthentication,
    workId: uuid.UUID,
) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    return JsonResponse({
        "run": build_run_payload(get_visible_runs(access).get(pk=workId), details=True)
    })


@_work_view
@require_POST
@request_budget(RequestBudget.CONTROL)
def stop_run(
    request: HttpRequest,
    authentication: WorkAuthentication,
    workId: uuid.UUID,
) -> JsonResponse:
    payload = parse_json_request(request, EmptyRequest)
    if isinstance(payload, JsonResponse):
        return payload
    with transaction.atomic():
        access = _get_access(request, authentication, write=True)
        run = get_visible_runs(access).select_for_update(of=("self",)).get(pk=workId)
        if control_job(run.job, JobControlAction.STOP, run=run):
            record_audit(
                AuditAction.RUN_STOP,
                actor=access.actor,
                organization=access.organization,
                target=run,
                channel=access.channel,
                metadata={"job_id": str(run.job_id)},
            )
        return JsonResponse({"run": build_run_payload(run, details=True)})


@_work_view
@require_GET
def rerun_options(
    request: HttpRequest,
    authentication: WorkAuthentication,
    workId: uuid.UUID,
) -> JsonResponse:
    access = _get_access(request, authentication, write=False)
    run = get_visible_runs(access).get(pk=workId)
    if run.ended_at is None or run.status == RunStatus.RUNNING:
        raise ValidationError(
            "This Run has not been confirmed as ended.", code="run_not_ended"
        )
    package = (
        Package.objects
        .filter(
            department_id=run.job.department_id,
            project_name_key=get_path_name_key(run.job.project_name),
        )
        .order_by("-uploaded_at", "-id")
        .first()
    )
    if package is None:
        raise Package.DoesNotExist
    return JsonResponse({
        "package_id": package.id,
        "executor_ids": [run.job.target_executor_id]
        if run.job.target_executor_id
        else [],
        "group_id": run.job.target_group_id,
        "original_job_active": run.job.state != JobState.FINISHED,
    })
