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
from django.db import DatabaseError
from django.db.models import Exists, OuterRef, Q
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.rate_limits import apply_executor_client_rate_limit
from console_project.contracts import JsonValue
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)

from executors.client_sessions import (
    InvalidExecutorSessionError,
    ExecutorClientAction,
    ExecutorClientResult,
    get_executor_session_identity,
    open_executor_client_request,
)
from executors.models import ExecutorSession

from .contracts import (
    WorkPollRequest,
    WorkEventRetentionRequest,
    WorkPermitRequest,
    WorkEventsRequest,
)
from .models import (
    JobState,
    AssignmentState,
    RunEventKind,
    RunResult,
    ExecutorWorkState,
    Assignment,
    Run,
    RunEvent,
)
from .dispatch import get_start_evidence_not_before, issue_start_permit
from .events import receive_event

if TYPE_CHECKING:
    from packages.preparation import PackagePreparationCommand

    from .transfers import PendingRunFileTransfer

_LOGGER = logging.getLogger("console.runs.protocol")


class WorkAssignmentPayload(TypedDict):
    id: uuid.UUID
    job_id: uuid.UUID
    run_id: uuid.UUID
    attempt_number: int
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


class ResolvedEventAssignment(TypedDict):
    assignment_id: uuid.UUID
    run_started: bool


class WorkEventRetentionResponse(TypedDict):
    resolved_assignments: list[ResolvedEventAssignment]


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
            "other_active_run_count": payload.other_active_run_count,
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
    if work.other_active_run_count != payload.other_active_run_count:
        work.other_active_run_count = payload.other_active_run_count
        listUpdateField.append("other_active_run_count")
    work.save(update_fields=listUpdateField)


def _poll(authentication: ExecutorClientResult, payload: WorkPollRequest) -> JsonResponse:
    from .transfers import get_pending_transfers
    from packages.preparation import claim_package_preparations

    def build_assignment_payload(assignment: Assignment) -> WorkAssignmentPayload:
        return {
            "id": assignment.id,
            "job_id": assignment.job_id,
            "run_id": assignment.run_id,
            "attempt_number": assignment.attempt_number,
            "package_id": assignment.job.package_id,
            "package_download_url": f"/api/clients/executor/packages/{assignment.job.package_id}/downloads/",
            "snapshot": {
                **assignment.job.run_snapshot,
                "schedule_name": assignment.job.request.schedule_name or None,
            },
        }

    session = authentication.session
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
            Q(stop_requested_at__isnull=False) | Q(job__stop_requested_at__isnull=False),
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
        "preparations": claim_package_preparations(authentication.access, session),
        "server_time": timezone.now(),
    }
    return JsonResponse(dictResponse)


def _check_event_retention(
    authentication: ExecutorClientResult, payload: WorkEventRetentionRequest
) -> JsonResponse:
    """Confirm settled original work without accepting, retrying or deleting any event."""
    session = authentication.session
    nonStartReceipts = RunEvent.objects.filter(
        assignment_id=OuterRef("pk"), kind=RunEventKind.NOT_STARTED
    )
    endedRuns = Run.objects.filter(
        assignment_id=OuterRef("pk"), ended_at__isnull=False
    ).exclude(result=RunResult.RUNNING)
    unsettledAssignments = Assignment.objects.filter(job_id=OuterRef("job_id")).filter(
        ~Q(state__in=(AssignmentState.FINISHED, AssignmentState.WITHDRAWN))
        | (
            Q(permit_expires_at__isnull=False)
            & ~Exists(nonStartReceipts)
            & ~Exists(endedRuns)
        )
    )
    unsettledRuns = Run.objects.filter(job_id=OuterRef("job_id")).filter(
        Q(ended_at__isnull=True) | Q(result=RunResult.RUNNING)
    )
    assignments = (
        Assignment.objects
        .filter(
            ~Exists(unsettledAssignments),
            ~Exists(unsettledRuns),
            pk__in=payload.assignment_ids,
            session_id=session.id,
            executor_id=session.executor_id,
            job__request__organization_id=authentication.access.organization.id,
            job__state=JobState.FINISHED,
            job__ended_at__isnull=False,
            job__retry_at__isnull=True,
        )
        .annotate(has_run=Exists(Run.objects.filter(assignment_id=OuterRef("pk"))))
        .order_by("id")
        .values_list("id", "has_run")
    )
    # A missing assignment is not evidence of completion (for example after backup restore).
    dictResponse: WorkEventRetentionResponse = {
        "resolved_assignments": [
            {"assignment_id": assignmentId, "run_started": boolHasRun}
            for assignmentId, boolHasRun in assignments
        ]
    }
    return JsonResponse(dictResponse)


@csrf_exempt
@never_cache
@require_POST
def executor_work_endpoint(request: HttpRequest, action: str) -> JsonResponse:
    try:
        intRetryAfter = apply_executor_client_rate_limit(
            request.META.get("REMOTE_ADDR", "")
        )
        if intRetryAfter:
            return build_rate_limited_response(intRetryAfter)
        identity = get_executor_session_identity(request.headers.get("Authorization", ""))
        requestClass = {
            "poll": WorkPollRequest,
            "permit": WorkPermitRequest,
            "events": WorkEventsRequest,
            "event-retention": WorkEventRetentionRequest,
        }[action]
        payload = parse_json_request(request, requestClass, maxBodyBytes=1024 * 1024)
        if isinstance(payload, JsonResponse):
            return payload
        if action != "events":
            with open_executor_client_request(
                identity=identity, action=ExecutorClientAction.HEARTBEAT
            ) as result:
                authentication = cast(ExecutorClientResult, result)
                if action == "poll":
                    return _poll(authentication, cast(WorkPollRequest, payload))
                if action == "event-retention":
                    return _check_event_retention(
                        authentication, cast(WorkEventRetentionRequest, payload)
                    )
                if action == "permit":
                    session = authentication.session
                    assignment = issue_start_permit(
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
        boolContactRecorded = False
        for event in cast(WorkEventsRequest, payload).events:
            try:
                with open_executor_client_request(
                    identity=identity,
                    action=ExecutorClientAction.HEARTBEAT,
                    recordContact=not boolContactRecorded,
                ) as result:
                    receive_event(cast(ExecutorClientResult, result).session, event)
                boolContactRecorded = True
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
