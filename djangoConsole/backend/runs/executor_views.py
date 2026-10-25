# FileName: executor_views.py
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
from django.db.models import Q
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
from operations.maintenance import ServiceMaintenanceError

from .contracts import (
    JobState,
    AssignmentState,
    RunEventKind,
    WorkSyncRequest,
    WorkPermitRequest,
    WorkEventsRequest,
)
from .models import Assignment
from .executor_state import update_executor_work_state
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
    snapshot: dict[str, JsonValue]


class WorkStopCommand(TypedDict):
    assignment_id: uuid.UUID
    run_id: uuid.UUID


class WorkSyncResponse(TypedDict):
    assignments: list[WorkAssignmentPayload]
    stop_requests: list[WorkStopCommand]
    file_transfers: list["PendingRunFileTransfer"]
    preparations: list["PackagePreparationCommand"]


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


def _sync(authentication: ExecutorClientResult, payload: WorkSyncRequest) -> JsonResponse:
    from .transfers import get_pending_transfers
    from packages.preparation import claim_package_preparations

    def build_assignment_payload(assignment: Assignment) -> WorkAssignmentPayload:
        return {
            "id": assignment.id,
            "job_id": assignment.job_id,
            "run_id": assignment.run_id,
            "attempt_number": assignment.attempt_number,
            "package_id": assignment.job.package_id,
            "snapshot": {
                **assignment.job.run_snapshot,
                "schedule_name": assignment.job.request.schedule_name or None,
            },
        }

    session = authentication.session
    update_executor_work_state(session, payload)
    if payload.received_assignment_id is not None:
        Assignment.objects.filter(
            pk=payload.received_assignment_id,
            executor_id=session.executor_id,
            session_id=session.id,
            received_at__isnull=True,
        ).update(received_at=timezone.now())

    listAssignment = list(
        Assignment.objects
        .filter(
            executor_id=session.executor_id,
            session_id=session.id,
            received_at__isnull=True,
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
            | Q(job__stop_requested_at__isnull=False)
            | Q(state=AssignmentState.WITHDRAWN),
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
    dictResponse: WorkSyncResponse = {
        "assignments": [build_assignment_payload(entry) for entry in listAssignment],
        "stop_requests": [
            {"assignment_id": entry["id"], "run_id": entry["run_id"]}
            for entry in listStop
        ],
        "file_transfers": get_pending_transfers(session.pk),
        "preparations": claim_package_preparations(authentication.access, session),
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
            "sync": WorkSyncRequest,
            "permit": WorkPermitRequest,
            "events": WorkEventsRequest,
        }[action]
        payload = parse_json_request(request, requestClass, maxBodyBytes=1024 * 1024)
        if isinstance(payload, JsonResponse):
            return payload
        if action != "events":
            with open_executor_client_request(
                identity=identity, action=ExecutorClientAction.HEARTBEAT
            ) as result:
                authentication = cast(ExecutorClientResult, result)
                if action == "sync":
                    return _sync(authentication, cast(WorkSyncRequest, payload))
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
            statusCode=503 if isinstance(e, ServiceMaintenanceError) else 409,
        )
    except DatabaseError:
        _LOGGER.exception("Executor control request could not commit.")
        return build_service_unavailable_response()
