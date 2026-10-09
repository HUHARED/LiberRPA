# FileName: protocol.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict, cast

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST

from accounts.rate_limits import apply_executor_client_rate_limit
from console_project.contracts import JsonValue
from console_project.http import (
    build_error_response,
    build_rate_limited_response,
    build_service_unavailable_response,
    parse_json_request,
)
from executors.client_sessions import (
    ExecutorClientAction,
    ExecutorClientResult,
    InvalidExecutorSessionError,
    get_locked_executor_session,
    open_executor_client_request,
)
from executors.models import ExecutorSession
from organizations.permissions import AccessChannel, resolve_organization_access

from .contracts import WorkEventsRequest, WorkPermitRequest, WorkPollRequest
from .models import Assignment, AssignmentState, ExecutorWorkState, JobState, RunEventKind
from .dispatch import get_start_evidence_not_before, issue_permission
from .events import receive_event

if TYPE_CHECKING:
    from packages.preparation import PackagePreparationCommand

    from .transfers import PendingRunFileTransfer

_LOGGER = logging.getLogger("console.runs.protocol")


class WorkAssignmentPayload(TypedDict):
    id: uuid.UUID
    job_id: uuid.UUID
    run_id: uuid.UUID
    attempt: int
    package_id: uuid.UUID
    package_download_url: str
    snapshot: dict[str, JsonValue]


class WorkStopCommand(TypedDict):
    assignment_id: uuid.UUID
    run_id: uuid.UUID


class WorkPollResponse(TypedDict):
    assignments: list[WorkAssignmentPayload]
    stop_requests: list[WorkStopCommand]
    file_transfers: list["PendingRunFileTransfer"]
    preparations: list["PackagePreparationCommand"]
    server_time: datetime


class WorkPermitResponse(TypedDict):
    assignment_id: uuid.UUID
    run_id: uuid.UUID
    permit_expires_at: datetime
    start_evidence_not_before: datetime
    server_time: datetime


class WorkEventRejection(TypedDict):
    event_id: uuid.UUID
    code: str
    message: str


class WorkEventsResponse(TypedDict):
    accepted_event_ids: list[uuid.UUID]
    rejected_events: list[WorkEventRejection]


@sensitive_variables()
def authenticate_executor_work(
    request: HttpRequest,
) -> ExecutorClientResult | JsonResponse:
    intRetryAfter = apply_executor_client_rate_limit(request.META.get("REMOTE_ADDR", ""))
    if intRetryAfter:
        return build_rate_limited_response(intRetryAfter)
    with open_executor_client_request(
        authorizationHeader=request.headers.get("Authorization", ""),
        action=ExecutorClientAction.HEARTBEAT,
    ) as authentication:
        result = cast(ExecutorClientResult, authentication)
        if result.session.executor_id is None:
            raise InvalidExecutorSessionError("Select an Executor first.")
        return result


def lock_executor_work(authentication: ExecutorClientResult) -> ExecutorSession:
    access = resolve_organization_access(
        actorId=authentication.access.actorId,
        organizationId=authentication.access.organization.id,
        channel=AccessChannel.EXECUTOR,
        forUpdate=True,
    )
    session = get_locked_executor_session(access, authentication.session.id)
    if session.executor_id is None:
        raise InvalidExecutorSessionError("The original association is unavailable.")
    return session


def update_executor_work_state(
    session: ExecutorSession, payload: WorkPollRequest
) -> None:
    """Save a validated report inside the caller's locked association transaction."""
    currentTime = timezone.now()
    listRunningRunId = [str(entry) for entry in payload.running_run_ids]
    work, boolCreated = ExecutorWorkState.objects.get_or_create(
        executor_id=session.executor_id,
        defaults={
            "session_id": session.id,
            "reported_at": currentTime,
            "running_run_ids": listRunningRunId,
            "local_waiting_count": payload.local_waiting_count,
            "local_running_count": payload.local_running_count,
        },
    )
    if boolCreated:
        return

    # Freshness is a new fact on every report; unchanged occupancy is not.
    work.reported_at = currentTime
    listUpdateField = ["reported_at"]
    if work.session_id != session.id:
        work.session_id = session.id
        listUpdateField.append("session_id")
    if work.running_run_ids != listRunningRunId:
        work.running_run_ids = listRunningRunId
        listUpdateField.append("running_run_ids")
    if work.local_waiting_count != payload.local_waiting_count:
        work.local_waiting_count = payload.local_waiting_count
        listUpdateField.append("local_waiting_count")
    if work.local_running_count != payload.local_running_count:
        work.local_running_count = payload.local_running_count
        listUpdateField.append("local_running_count")
    work.save(update_fields=listUpdateField)


def _poll(authentication: ExecutorClientResult, payload: WorkPollRequest) -> JsonResponse:
    from .transfers import get_pending_transfers
    from packages.preparation import get_preparation_commands

    def build_assignment_payload(assignment: Assignment) -> WorkAssignmentPayload:
        return {
            "id": assignment.id,
            "job_id": assignment.job_id,
            "run_id": assignment.run_id,
            "attempt": assignment.attempt,
            "package_id": assignment.job.package_id,
            "package_download_url": f"/api/clients/executor/packages/{assignment.job.package_id}/downloads/",
            "snapshot": {
                **assignment.job.run_snapshot,
                "schedule_name": assignment.job.request.schedule_name or None,
            },
        }

    with transaction.atomic():
        session = lock_executor_work(authentication)
        update_executor_work_state(session, payload)
        listAssignment = list(
            Assignment.objects
            .filter(
                session_id=session.id,
                state=AssignmentState.PREPARING,
                job__state=JobState.PREPARING,
                job__closed_at__isnull=True,
                job__stop_requested_at__isnull=True,
            )
            .select_related("job__request")
            .order_by("created_at", "id")[:1]
        )
        listStop = list(
            Assignment.objects
            .filter(
                Q(stop_requested_at__isnull=False)
                | Q(job__stop_requested_at__isnull=False),
                session_id=session.id,
            )
            .exclude(state=AssignmentState.FINISHED)
            # A non-start receipt ends redelivery without changing withdrawal into preparation failure.
            .exclude(
                state=AssignmentState.WITHDRAWN,
                events__kind=RunEventKind.NOT_STARTED,
            )
            .exclude(
                state=AssignmentState.WITHDRAWN,
                permit_expires_at__isnull=True,
                events__kind=RunEventKind.PREPARATION_FAILED,
            )
            .values("id", "run_id")
        )
        dictResponse: WorkPollResponse = {
            "assignments": [build_assignment_payload(entry) for entry in listAssignment],
            "stop_requests": [
                {"assignment_id": entry["id"], "run_id": entry["run_id"]}
                for entry in listStop
            ],
            "file_transfers": get_pending_transfers(session.pk),
            "preparations": get_preparation_commands(authentication.access, session),
            "server_time": timezone.now(),
        }
        return JsonResponse(dictResponse)


@csrf_exempt
@never_cache
@require_POST
def executor_work_endpoint(request: HttpRequest, action: str) -> JsonResponse:
    try:
        authentication = authenticate_executor_work(request)
        if isinstance(authentication, JsonResponse):
            return authentication
        requestClass = {
            "poll": WorkPollRequest,
            "permit": WorkPermitRequest,
            "events": WorkEventsRequest,
        }[action]
        payload = parse_json_request(request, requestClass, maxBodyBytes=1024 * 1024)
        if isinstance(payload, JsonResponse):
            return payload
        if action == "poll":
            return _poll(authentication, cast(WorkPollRequest, payload))
        if action == "permit":
            with transaction.atomic():
                session = lock_executor_work(authentication)
                assignment = issue_permission(
                    session, cast(WorkPermitRequest, payload).assignment_id
                )
                if assignment.permit_expires_at is None:
                    return build_error_response(
                        "assignment_skipped"
                        if assignment.state == AssignmentState.FINISHED
                        else "assignment_requeued",
                        assignment.reason,
                        statusCode=409,
                    )
                dictPermit: WorkPermitResponse = {
                    "assignment_id": assignment.id,
                    "run_id": assignment.run_id,
                    "permit_expires_at": assignment.permit_expires_at,
                    "start_evidence_not_before": get_start_evidence_not_before(
                        assignment.permit_expires_at
                    ),
                    "server_time": timezone.now(),
                }
                return JsonResponse(dictPermit)
        listAccepted: list[uuid.UUID] = []
        listRejected: list[WorkEventRejection] = []
        for event in cast(WorkEventsRequest, payload).events:
            try:
                with transaction.atomic():
                    session = lock_executor_work(authentication)
                    receive_event(session, event)
                listAccepted.append(event.event_id)
            except (ValidationError, ObjectDoesNotExist) as e:
                listRejected.append({
                    "event_id": event.event_id,
                    "code": getattr(e, "code", None) or "invalid_event",
                    "message": "; ".join(e.messages)
                    if isinstance(e, ValidationError)
                    else "The original assignment is unavailable.",
                })
        dictEvents: WorkEventsResponse = {
            "accepted_event_ids": listAccepted,
            "rejected_events": listRejected,
        }
        return JsonResponse(dictEvents)
    except InvalidExecutorSessionError:
        return build_error_response(
            "executor_authentication_required",
            "A valid original Executor association is required.",
            statusCode=401,
        )
    except PermissionDenied as e:
        return build_error_response("executor_access_required", str(e), statusCode=403)
    except ObjectDoesNotExist:
        return build_error_response(
            "assignment_not_found",
            "The original assignment is unavailable.",
            statusCode=404,
        )
    except ValidationError as e:
        return build_error_response(
            getattr(e, "code", None) or "invalid_executor_work",
            "; ".join(e.messages),
            statusCode=409,
        )
    except DatabaseError:
        _LOGGER.exception("Executor control request could not commit.")
        return build_service_unavailable_response()
