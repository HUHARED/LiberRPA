# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import copy
import logging
import uuid
from typing import cast

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods

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
from executors.http import get_executor_request_membership, lock_executor_write_access
from operations.audit import record_audit
from organizations.models import Membership
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    resolve_organization_access,
)
from packages.models import Package
from packages.runtime import build_run_settings

from .contracts import EmptyRequest, JobControlRequest, JobCreationRequest
from .models import JobSource, JobState
from .queries import (
    build_job_payload,
    build_job_payloads,
    build_run_payload,
    get_visible_jobs,
    get_history_departments,
    get_visible_runs,
    get_matching_run_ids,
    list_work,
)
from .admission import get_existing_request, accept_request
from .services import control_job

_LOGGER = logging.getLogger("console.runs")
_SET_RUN_OVERRIDE_FIELDS = frozenset({
    "retry_count",
    "timeout_min",
    "builtin_log_level",
    "builtin_record_video",
    "builtin_stop_shortcut",
    "builtin_highlight_ui",
    "custom_prj_args",
    "custom_arg_assets",
    "run_conflict_policy",
    "priority",
    "run_email",
})


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
            statusCode=400,
        )
    _LOGGER.exception("Run request failed.")
    return build_service_unavailable_response()


def _get_authentication(
    request: HttpRequest,
) -> ApiKeyAuthenticationContext | Membership | JsonResponse:
    if request.headers.get("Authorization"):
        authentication = authenticate_resource_request(request)
        if isinstance(authentication, JsonResponse):
            return authentication
        if not isinstance(authentication, ApiKeyAuthenticationContext):
            raise PermissionDenied("This endpoint requires a web session or API key.")
        return authentication
    return get_executor_request_membership(request)


def _get_access(
    request: HttpRequest,
    authentication: ApiKeyAuthenticationContext | Membership,
    *,
    write: bool,
) -> OrganizationAccessContext:
    if isinstance(authentication, ApiKeyAuthenticationContext):
        return (
            lock_resource_write_access(authentication) if write else authentication.access
        )
    if write:
        return lock_executor_write_access(request, authentication)
    return resolve_organization_access(
        actorId=authentication.user_id,
        organizationId=authentication.organization_id,
        channel=AccessChannel.SESSION,
    )


def _get_request_settings(
    package: Package, payload: JobCreationRequest, *, apiKey: bool
) -> dict:
    """Apply invocation overrides without changing Package defaults or API input permissions."""
    dictOverrideSettings = payload.settings or {}
    if not dictOverrideSettings.keys() <= _SET_RUN_OVERRIDE_FIELDS:
        raise ValidationError(
            "One or more settings cannot be overridden for a single run."
        )
    if apiKey and any(
        strField in dictOverrideSettings
        for strField in ("custom_prj_args", "custom_arg_assets")
    ):
        raise ValidationError(
            "Use custom_args for API inputs; argument lists and bindings cannot be overridden."
        )
    dictSettings = copy.deepcopy(build_run_settings(package))
    dictSettings.update(dictOverrideSettings)
    if not apiKey:
        if payload.custom_args is not None:
            raise ValidationError("Use run settings for a web request.")
        return dictSettings
    dictOverride = payload.custom_args or {}
    if not set(dictOverride).issubset(set(package.api_input_keys)):
        raise ValidationError(
            "One or more input names are not enabled for API overrides."
        )
    listArgument = dictSettings["custom_prj_args"]
    dictPosition = {entry[0]: intIndex for intIndex, entry in enumerate(listArgument)}
    listBinding = dictSettings.get("custom_arg_assets") or [None] * len(listArgument)
    for strName, value in dictOverride.items():
        if strName not in dictPosition:
            raise ValidationError(
                "An API input name is no longer present in the Package."
            )
        intIndex = dictPosition[strName]
        listArgument[intIndex][1] = value
        listBinding[intIndex] = None
    dictSettings["custom_arg_assets"] = listBinding
    return dictSettings


def _process_work_request(
    request: HttpRequest, *, action: str, workId: uuid.UUID | None = None
) -> JsonResponse:
    try:
        authentication = _get_authentication(request)
        if isinstance(authentication, JsonResponse):
            return authentication
        if request.method == "GET":
            access = _get_access(request, authentication, write=False)
            if action == "departments":
                return JsonResponse({"departments": get_history_departments(access)})
            if action == "run-selection":
                return JsonResponse({
                    "run_ids": get_matching_run_ids(access, request.GET)
                })
            if action in ("jobs", "runs"):
                return JsonResponse(list_work(access, request.GET, runs=action == "runs"))
            if action == "job":
                return JsonResponse({
                    "job": build_job_payload(
                        get_visible_jobs(access).get(pk=workId), details=True
                    )
                })
            run = get_visible_runs(access).get(pk=workId)
            if action == "rerun":
                package = (
                    Package.objects
                    .filter(
                        department_id=run.job.department_id,
                        project_name=run.job.project_name,
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
            return JsonResponse({"run": build_run_payload(run, details=True)})
        requestClass = (
            JobCreationRequest
            if action == "jobs"
            else JobControlRequest
            if action == "control"
            else EmptyRequest
        )
        payload = parse_json_request(request, requestClass, maxBodyBytes=2 * 1024 * 1024)
        if isinstance(payload, JsonResponse):
            return payload
        with transaction.atomic():
            access = _get_access(request, authentication, write=True)
            if action == "jobs":
                creationRequest = cast(JobCreationRequest, payload)
                source = (
                    JobSource.API
                    if access.channel == AccessChannel.API_KEY
                    else JobSource.MANUAL
                )
                previous = get_existing_request(
                    access,
                    source=source,
                    clientRequestId=creationRequest.request_id,
                    requestContent=creationRequest.model_dump(mode="json"),
                )
                if previous is not None:
                    return JsonResponse({
                        "request_id": previous.client_request_id,
                        "job_request_id": previous.id,
                        "jobs": build_job_payloads(
                            previous.jobs.select_related("request")
                        ),
                    })
                package = Package.objects.select_related("department").get(
                    pk=creationRequest.package_id,
                    department__organization=access.organization,
                )
                dictSettings = _get_request_settings(
                    package,
                    creationRequest,
                    apiKey=access.channel == AccessChannel.API_KEY,
                )
                jobRequest = accept_request(
                    organizationId=access.organization.id,
                    departmentId=package.department_id,
                    packageId=package.id,
                    settings=dictSettings,
                    executorIds=creationRequest.executor_ids,
                    groupId=creationRequest.group_id,
                    source=source,
                    actorId=access.actorId,
                    clientRequestId=creationRequest.request_id,
                    requestContent=creationRequest.model_dump(mode="json"),
                )
                return JsonResponse(
                    {
                        "request_id": jobRequest.client_request_id,
                        "job_request_id": jobRequest.id,
                        "jobs": build_job_payloads(
                            jobRequest.jobs.select_related("request")
                        ),
                    },
                    status=201,
                )
            if action == "control":
                controlRequest = cast(JobControlRequest, payload)
                job = (
                    get_visible_jobs(access)
                    .select_for_update(of=("self",))
                    .get(pk=workId)
                )
                strPreviousState = job.state
                control_job(job, controlRequest.action)
                if strPreviousState != job.state:
                    record_audit(
                        f"job.{controlRequest.action}",
                        actor=access.actor,
                        organization=access.organization,
                        target=job,
                        channel=access.channel,
                        metadata={"previous_state": strPreviousState, "state": job.state},
                    )
                return JsonResponse({"job": build_job_payload(job, details=True)})
            run = get_visible_runs(access).select_for_update(of=("self",)).get(pk=workId)
            control_job(run.job, "stop", run=run)
            record_audit(
                "run.stop",
                actor=access.actor,
                organization=access.organization,
                target=run,
                channel=access.channel,
                metadata={"job_id": str(run.job_id)},
            )
            return JsonResponse({"run": build_run_payload(run, details=True)})
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


@csrf_exempt
@never_cache
@require_http_methods(["GET", "POST"])
def work_endpoint(
    request: HttpRequest, action: str, workId: uuid.UUID | None = None
) -> JsonResponse:
    """Explicit API keys do not use CSRF; cookie-authenticated writes always do."""
    setReadOnly = {"job", "run", "rerun", "runs", "run-selection", "departments"}
    if action in setReadOnly and request.method != "GET":
        return build_error_response("method_not_allowed", "Use GET.", statusCode=405)
    if action in {"control", "stop"} and request.method != "POST":
        return build_error_response("method_not_allowed", "Use POST.", statusCode=405)
    if request.headers.get("Authorization"):
        return _process_work_request(request, action=action, workId=workId)
    return csrf_protect(_process_work_request)(request, action=action, workId=workId)
