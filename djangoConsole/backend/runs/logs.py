# FileName: logs.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, cast

from django.conf import settings
from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from pydantic import Field

from accounts.models import User
from accounts.resource_authentication import (
    NativeResourceAuthenticationContext,
    authenticate_resource_request,
    lock_resource_write_access,
)
from accounts.session_revocation import lock_session_write_access
from console_project.constants import RunLogLevel
from console_project.contracts import JsonRequest, JsonValue
from console_project.http import build_error_response, parse_json_request
from console_project.validators import validate_json_text
from operations.audit import record_audit
from organizations.models import DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
    get_current_membership,
    resolve_organization_access,
)

from .models import JobState, Run, RunLog, RunLogState

_INT_UPLOAD_BYTES = 1024 * 1024
_INT_ENTRY_BYTES = 256 * 1024
_INT_PREVIEW_BYTES = 512 * 1024
_SET_BUILTIN_LOG_KEYS = {
    "logId",
    "timestamp",
    "level",
    "message",
    "userName",
    "machineName",
    "processName",
    "fileName",
    "lineNo",
    "projectName",
}


class LogBatchRequest(JsonRequest):
    logs: list[str] = Field(max_length=1000)
    complete: bool = False


class ClearLogsRequest(JsonRequest):
    run_ids: list[Annotated[uuid.UUID, Field(strict=False)]] = Field(
        min_length=1, max_length=20000
    )


def get_web_access(
    request: HttpRequest, *, forUpdate: bool = False
) -> OrganizationAccessContext:
    if not request.user.is_authenticated:
        raise PermissionDenied("Sign in to continue.")
    user = cast(User, request.user)
    membership = get_current_membership(actorId=user.pk)
    if forUpdate:
        return lock_session_write_access(
            user.pk,
            membership.organization_id,
            AccessChannel.SESSION,
            request.session.get(HASH_SESSION_KEY, ""),
            request.session.get_expiry_date(),
        )
    return resolve_organization_access(
        actorId=user.pk,
        organizationId=membership.organization_id,
        channel=AccessChannel.SESSION,
    )


def get_accessible_run(access: OrganizationAccessContext, runId: uuid.UUID) -> Run:
    run = Run.objects.select_related("job__request", "assignment").get(
        pk=runId,
        job__request__organization=access.organization,
    )
    # Administrators may inspect retained history belonging to a deleted department.
    if (
        not access.isOrgAdmin
        and not get_authorized_departments(
            access,
            requiredRole=DepartmentRole.OPERATOR,
        )
        .filter(pk=run.job.department_id)
        .exists()
    ):
        raise PermissionDenied("Run access is unavailable.")
    return run


def _validate_log_text(value: JsonValue) -> None:
    # Log messages retain ordinary JSON numbers, including integers above the API safe range.
    if isinstance(value, dict):
        for strKey, child in value.items():
            validate_json_text(strKey)
            _validate_log_text(child)
    elif isinstance(value, list):
        for child in value:
            _validate_log_text(child)
    elif isinstance(value, str):
        validate_json_text(value)


def _build_run_log(entryText: str, run: Run) -> RunLog:
    def parse_log_object(fieldPairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        dictField: dict[str, JsonValue] = {}
        for strKey, value in fieldPairs:
            if strKey in dictField:
                raise ValueError("Duplicate JSON fields are not allowed.")
            dictField[strKey] = value
        return dictField

    try:
        intSourceBytes = len(entryText.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError("The log entry is not valid UTF-8.") from None
    if intSourceBytes > _INT_ENTRY_BYTES:
        raise ValueError("The log entry exceeds 256 KiB.")
    try:
        value = cast(JsonValue, json.loads(entryText, object_pairs_hook=parse_log_object))
    except (ValueError, RecursionError):
        raise ValueError("Use a valid JSON log entry without duplicate fields.") from None
    if not isinstance(value, dict):
        raise ValueError("A log entry must be an object.")
    if not _SET_BUILTIN_LOG_KEYS.issubset(value):
        raise ValueError("All MachineLog fields are required.")
    dictText: dict[str, str] = {}
    for strKey in (
        "logId",
        "timestamp",
        "level",
        "userName",
        "machineName",
        "processName",
        "fileName",
        "projectName",
    ):
        fieldValue = value[strKey]
        if not isinstance(fieldValue, str):
            raise ValueError(f"The {strKey} field must be text.")
        dictText[strKey] = fieldValue
    try:
        logId = uuid.UUID(dictText["logId"])
    except ValueError:
        raise ValueError("A UUID4 logId is required.") from None
    if logId.version != 4:
        raise ValueError("A UUID4 logId is required.")
    try:
        timestamp = datetime.fromisoformat(dictText["timestamp"])
        if timezone.is_naive(timestamp):
            raise ValueError
        timestamp = timestamp.astimezone(UTC)
    except (ValueError, OverflowError):
        raise ValueError("Use an ISO timestamp with a UTC offset.") from None
    try:
        level = RunLogLevel(dictText["level"])
    except ValueError:
        raise ValueError("Use a supported MachineLog level.") from None
    intLineNo = value["lineNo"]
    if type(intLineNo) is not int or not 0 <= intLineNo <= 2**63 - 1:
        raise ValueError("lineNo must be a nonnegative 64-bit integer.")
    dictCustomFields: dict[str, str] = {}
    for strKey, fieldValue in value.items():
        if strKey not in _SET_BUILTIN_LOG_KEYS:
            if not strKey.isidentifier() or not isinstance(fieldValue, str):
                raise ValueError(
                    "Custom log fields must use identifier names and text values."
                )
            dictCustomFields[strKey] = fieldValue
    try:
        _validate_log_text(value)
        intBytes = len(
            json.dumps(
                value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
        )
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError(
            "Use finite JSON values and valid UTF-8 text without NUL characters."
        ) from None
    if intBytes > _INT_ENTRY_BYTES:
        raise ValueError("The log entry exceeds 256 KiB.")
    return RunLog(
        log_id=logId,
        run=run,
        timestamp=timestamp,
        level=level,
        user_name=dictText["userName"],
        machine_name=dictText["machineName"],
        process_name=dictText["processName"],
        file_name=dictText["fileName"],
        line_no=intLineNo,
        project_name=dictText["projectName"],
        message=value["message"],
        custom_fields=dictCustomFields,
        byte_count=intBytes,
    )


@csrf_exempt
@never_cache
@require_POST
def upload_logs(request: HttpRequest, runId: uuid.UUID) -> HttpResponse:
    authentication = authenticate_resource_request(request)
    if isinstance(authentication, JsonResponse):
        return authentication
    if (
        not isinstance(authentication, NativeResourceAuthenticationContext)
        or authentication.access.channel != AccessChannel.EXECUTOR
    ):
        return build_error_response(
            "executor_required", "An Executor session is required.", statusCode=403
        )
    payload = parse_json_request(request, LogBatchRequest, maxBodyBytes=_INT_UPLOAD_BYTES)
    if isinstance(payload, JsonResponse):
        return payload
    try:
        with transaction.atomic():
            access = lock_resource_write_access(authentication)
            run = Run.objects.select_related("job__request", "assignment").get(
                pk=runId,
                job__request__organization=access.organization,
                assignment__session_id=authentication.sessionId,
                assignment__actor_id=access.actorId,
            )
            if run.logs_cleared_at is not None:
                return JsonResponse({
                    "accepted": True,
                    "accepting": False,
                    "saved": [],
                    "existing": [],
                    "rejected": [],
                })
            runLogQuery = RunLog.objects.filter(
                run__job__request__organization=access.organization
            )
            intUsedBytes = runLogQuery.aggregate(total=Sum("byte_count"))["total"] or 0
            boolNewGroup = not run.logs.exists()
            if (
                boolNewGroup
                and runLogQuery.values("run_id").distinct().count()
                >= settings.CONSOLE_LIMITS.maxRunLogGroupsPerOrganization
            ):
                return build_error_response(
                    "run_log_capacity",
                    "The organization log group limit has been reached.",
                    statusCode=409,
                )
            listSaved: list[str] = []
            listExisting: list[str] = []
            listRejected: list[dict] = []
            for intIndex, strEntry in enumerate(payload.logs):
                try:
                    runLog = _build_run_log(strEntry, run)
                except ValueError as e:
                    listRejected.append({
                        "index": intIndex,
                        "reason": str(e),
                    })
                    continue
                existingLog = RunLog.objects.filter(log_id=runLog.log_id).first()
                if existingLog is not None:
                    if existingLog.run_id == run.pk:
                        listExisting.append(str(runLog.log_id))
                    else:
                        listRejected.append({
                            "index": intIndex,
                            "reason": "This log identity belongs to another Run.",
                        })
                    continue
                if (
                    intUsedBytes + runLog.byte_count
                    > settings.CONSOLE_LIMITS.maxRunLogBytesPerOrganization
                ):
                    # Roll back this batch; the sender retains original identities for retry after cleanup.
                    raise ValidationError(
                        "The organization log byte limit has been reached."
                    )
                runLog.save(force_insert=True)
                intUsedBytes += runLog.byte_count
                listSaved.append(str(runLog.log_id))
            if payload.complete:
                RunLogState.objects.update_or_create(run=run, defaults={"complete": True})
            return JsonResponse({
                "accepted": True,
                "accepting": True,
                "saved": listSaved,
                "existing": listExisting,
                "rejected": listRejected,
            })
    except (PermissionDenied, ObjectDoesNotExist):
        return build_error_response(
            "run_unavailable",
            "The original Run and client association are required.",
            statusCode=403,
        )
    except ValidationError:
        return build_error_response(
            "run_log_capacity",
            "Log capacity is exhausted; retry after cleanup.",
            statusCode=409,
        )


@never_cache
@require_GET
def list_logs(request: HttpRequest, runId: uuid.UUID) -> HttpResponse:
    try:
        access = get_web_access(request)
        run = get_accessible_run(access, runId)
        if set(request.GET) - {"before", "after"} or (
            "before" in request.GET and "after" in request.GET
        ):
            raise ValueError
        strField = "after" if "after" in request.GET else "before"
        strCursor = request.GET.get(strField)
        intCursor = int(strCursor) if strCursor is not None else None
        if intCursor is not None and intCursor < 0:
            raise ValueError
        query = run.logs.all()
        if intCursor is not None:
            query = query.filter(**{
                "sequence__gt" if strField == "after" else "sequence__lt": intCursor
            })
        listLog: list[dict[str, object]] = []
        intTotalBytes = 0
        boolMore = False
        dictResponse: dict[str, object] = {
            "logs": [],
            "before_cursor": None,
            "after_cursor": intCursor or 0,
            "has_more": False,
            "cleared": run.logs_cleared_at is not None,
            "complete": RunLogState.objects.filter(run=run, complete=True).exists(),
        }
        intBeforeCursor: int | None = None
        intAfterCursor = 0
        for log in query.order_by("sequence" if strField == "after" else "-sequence")[
            :501
        ]:
            if len(listLog) == 500:
                boolMore = True
                break
            dictLog: dict[str, object] = {
                "log_id": str(log.log_id),
                "sequence": log.sequence,
                "timestamp": log.timestamp.isoformat(),
                "received_at": log.received_at.isoformat(),
                "level": log.level,
                "user_name": log.user_name,
                "machine_name": log.machine_name,
                "process_name": log.process_name,
                "file_name": log.file_name,
                "line_no": str(log.line_no),
                "project_name": log.project_name,
                # Browser previews must not parse message numbers into JavaScript Number.
                "message_text": log.message
                if isinstance(log.message, str)
                else json.dumps(
                    log.message,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ),
                "custom_fields": log.custom_fields,
            }
            intBytes = len(
                json.dumps(dictLog, ensure_ascii=False, separators=(",", ":")).encode()
            )
            intBeforeCursor = (
                min(intBeforeCursor, log.sequence)
                if intBeforeCursor is not None
                else log.sequence
            )
            intAfterCursor = max(intAfterCursor, log.sequence)
            dictHeader = dictResponse | {
                "before_cursor": intBeforeCursor,
                "after_cursor": intAfterCursor,
            }
            intHeaderBytes = len(
                json.dumps(dictHeader, ensure_ascii=False, separators=(",", ":")).encode()
            )
            intContentBytes = intTotalBytes + intBytes + (1 if listLog else 0)
            if intHeaderBytes + intContentBytes > _INT_PREVIEW_BYTES:
                boolMore = True
                break
            listLog.append(dictLog)
            intTotalBytes = intContentBytes
            dictResponse = dictHeader
        dictResponse["logs"] = listLog
        dictResponse["has_more"] = boolMore
        return JsonResponse(
            dictResponse,
            json_dumps_params={"ensure_ascii": False, "separators": (",", ":")},
        )
    except (PermissionDenied, ObjectDoesNotExist):
        return build_error_response(
            "run_unavailable", "Run access is unavailable.", statusCode=403
        )
    except ValueError:
        return build_error_response(
            "invalid_cursor",
            "Use one nonnegative before or after receive cursor.",
            statusCode=400,
        )


@never_cache
@require_POST
def clear_logs(request: HttpRequest) -> HttpResponse:
    payload = parse_json_request(
        request, ClearLogsRequest, maxBodyBytes=_INT_UPLOAD_BYTES
    )
    if isinstance(payload, JsonResponse):
        return payload
    try:
        with transaction.atomic():
            access = get_web_access(request, forUpdate=True)
            listSkipped = []
            listFailed = []
            intCleared = 0
            for runId in dict.fromkeys(payload.run_ids):
                try:
                    run = get_accessible_run(access, runId)
                except (PermissionDenied, ObjectDoesNotExist):
                    listFailed.append({
                        "id": str(runId),
                        "reason": "Run access is unavailable.",
                    })
                    continue
                if run.job.state != JobState.FINISHED:
                    listSkipped.append({
                        "id": str(runId),
                        "reason": "This Job is still active or awaiting review.",
                    })
                    continue
                run.logs.all().delete()
                run.logs_cleared_at = timezone.now()
                run.save(update_fields=["logs_cleared_at"])
                record_audit(
                    "run.clear_logs",
                    actor=access.actor,
                    organization=access.organization,
                    target=run,
                )
                intCleared += 1
            return JsonResponse({
                "cleared": intCleared,
                "skipped": listSkipped,
                "failed": listFailed,
            })
    except PermissionDenied:
        return build_error_response(
            "run_access_required", "Run access is unavailable.", statusCode=403
        )
