# FileName: transfers.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import asyncio
import json
import queue
import re
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from http.cookies import SimpleCookie
from typing import TypedDict, cast

from asgiref.sync import sync_to_async
from asgiref.typing import (
    ASGI3Application,
    ASGIReceiveCallable,
    ASGISendCallable,
    ASGISendEvent,
    HTTPScope,
    Scope,
)
from django.conf import settings
from django.contrib.auth import get_user
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import Field

from accounts.api_key_authentication import InvalidApiKeyError
from accounts.resource_authentication import (
    InvalidResourceCredentialError,
    NativeResourceAuthenticationContext,
    authenticate_resource,
    lock_resource_write_access,
    authenticate_resource_request,
)
from console_project.contracts import JsonRequest
from console_project.http import build_error_response, parse_json_request
from executors.contracts import ExecutorAssociationStatus
from executors.session_state import (
    get_executor_association_status,
    get_executor_sessions,
    is_executor_session_current,
)
from file_storage.services import FileOperationError, require_download_slot
from organizations.http import get_request_access
from organizations.permissions import AccessChannel

from .contracts import RecordingStatus, RunFileKind, RunFileRequest
from .models import Run, RunFileTransfer
from .queries import get_visible_runs
from .control_notifications import notify_executor_control

_INT_CHUNK_BYTES = 64 * 1024
_INT_BYTES_PER_SECOND = 5 * 1024 * 1024
_INT_PREPARATION_SECONDS = 60
_INT_TRANSFER_SECONDS = 30 * 60
_INT_IDLE_SECONDS = 60
_DICT_MAX_FILE_BYTES: dict[RunFileKind, int] = {
    RunFileKind.LOGS: 2 * 1024 * 1024 * 1024,
    RunFileKind.VIDEO: 512 * 1024 * 1024,
    RunFileKind.SUBTITLES: 10 * 1024 * 1024,
}
_DICT_TICKET: dict[uuid.UUID, "TransferTicket"] = {}
_LOCK_TICKET = threading.Lock()
_DICT_RATE_TIME: dict[uuid.UUID, float] = {}


class TransferState(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    STREAMING = "streaming"
    FINISHED = "finished"


@dataclass
class TransferTicket:
    id: uuid.UUID
    organizationId: uuid.UUID
    actorId: uuid.UUID
    sessionId: uuid.UUID
    runId: uuid.UUID
    kind: RunFileKind
    expiresAt: float
    readyEvent: threading.Event = field(default_factory=threading.Event)
    consumerEvent: threading.Event = field(default_factory=threading.Event)
    canceledEvent: threading.Event = field(default_factory=threading.Event)
    chunks: queue.Queue[bytes | None] = field(
        default_factory=lambda: queue.Queue(maxsize=8)
    )
    state: TransferState = TransferState.WAITING
    sizeBytes: int = 0
    filename: str = ""
    contentType: str = "application/octet-stream"
    error: str = ""


class PendingRunFileTransfer(TypedDict):
    id: str
    run_id: str
    kind: RunFileKind
    expires_at: str


class RunFileAvailability(TypedDict):
    available: bool
    reason: str
    size_bytes: int | None


def build_run_file_availability(run: Run) -> dict[RunFileKind, RunFileAvailability]:
    """Describe known source eligibility; actual local files are checked by the original client."""
    strCommonReason = ""
    if run.ended_at is None:
        strCommonReason = (
            "Original files are available only after this Run has a confirmed end."
        )
    else:
        currentTime = timezone.now()
        session = (
            get_executor_sessions(run.job.request.organization_id)
            .filter(
                pk=run.assignment.session_id,
                user_id=run.assignment.actor_id,
                executor_id=run.assignment.executor_id,
            )
            .first()
        )
        if session is None or not is_executor_session_current(
            session, currentTime=currentTime
        ):
            strCommonReason = "The original Executor client session is no longer valid."
        elif (
            get_executor_association_status(session, currentTime=currentTime)
            != ExecutorAssociationStatus.ONLINE
        ):
            strCommonReason = "The original Executor client is offline."

    boolRecordingReady = run.recording.get("status") == RecordingStatus.READY
    boolRecordingEnabled = bool(run.job.run_snapshot.get("builtin_record_video", False))
    dictSize = {
        RunFileKind.LOGS: None,
        RunFileKind.VIDEO: cast(int | None, run.recording.get("videoSizeBytes")),
        RunFileKind.SUBTITLES: cast(int | None, run.recording.get("subtitleSizeBytes")),
    }
    dictAvailability: dict[RunFileKind, RunFileAvailability] = {}
    for kind in RunFileKind:
        strReason = strCommonReason
        intSizeBytes = dictSize[kind]
        if not strReason and boolRecordingEnabled and not boolRecordingReady:
            strReason = (
                "Recording or finalization did not complete successfully. Retrieve available files on the Executor computer."
                if run.recording.get("status") == RecordingStatus.UNAVAILABLE
                else "Wait until this Run's recording has been finalized."
            )
        if not strReason and kind != RunFileKind.LOGS and not boolRecordingReady:
            strReason = "This Run has no completed recording available."
        if not strReason and kind == RunFileKind.SUBTITLES and intSizeBytes is None:
            strReason = "This Run has no subtitle file available."
        if (
            not strReason
            and intSizeBytes is not None
            and intSizeBytes > _DICT_MAX_FILE_BYTES[kind]
        ):
            intLimitMiB = _DICT_MAX_FILE_BYTES[kind] // (1024 * 1024)
            strReason = f"This file exceeds the {intLimitMiB} MiB download limit. Retrieve it on the Executor computer."
        dictAvailability[kind] = {
            "available": not bool(strReason),
            "reason": strReason,
            "size_bytes": intSizeBytes,
        }
    return dictAvailability


class FileReadyRequest(JsonRequest):
    size_bytes: int = Field(default=0, ge=0, le=2 * 1024 * 1024 * 1024)
    filename: str = Field(default="download", max_length=180)
    error: str = Field(default="", max_length=1000)


def _cancel_ticket(ticket: TransferTicket, message: str) -> None:
    with _LOCK_TICKET:
        ticket.error = message
        ticket.canceledEvent.set()
        ticket.readyEvent.set()
        ticket.consumerEvent.set()


def _get_ticket(transferId: uuid.UUID) -> TransferTicket:
    with _LOCK_TICKET:
        ticket = _DICT_TICKET.get(transferId)
    if (
        ticket is None
        or ticket.expiresAt <= time.monotonic()
        or ticket.canceledEvent.is_set()
    ):
        raise PermissionDenied("The file transfer has expired or is unavailable.")
    return ticket


def _discard_ticket(ticket: TransferTicket) -> None:
    with _LOCK_TICKET:
        ticket.canceledEvent.set()
        ticket.readyEvent.set()
        ticket.consumerEvent.set()
    RunFileTransfer.objects.filter(pk=ticket.id).delete()

    def remove_ticket() -> None:
        with _LOCK_TICKET:
            _DICT_TICKET.pop(ticket.id, None)
            if not any(
                other.organizationId == ticket.organizationId
                for other in _DICT_TICKET.values()
            ):
                _DICT_RATE_TIME.pop(ticket.organizationId, None)

    # Keep canceled tickets retryable if the database delete or its transaction fails.
    transaction.on_commit(remove_ticket)


def _expire_tickets() -> None:
    # Reclaim before admission as well as polling; an offline source may never poll again.
    with _LOCK_TICKET:
        floatCurrentTime = time.monotonic()
        listExpired = [
            ticket
            for ticket in _DICT_TICKET.values()
            if ticket.expiresAt <= floatCurrentTime or ticket.canceledEvent.is_set()
        ]
        for ticket in listExpired:
            # Ready uses the same lock, so an expired reservation cannot be revived.
            ticket.canceledEvent.set()
    for ticket in listExpired:
        _discard_ticket(ticket)


def get_pending_transfers(sessionId: uuid.UUID) -> list[PendingRunFileTransfer]:
    # Tickets are short-lived relay state, never a durable download queue.
    _expire_tickets()
    with _LOCK_TICKET:
        listTicket = list(_DICT_TICKET.values())
    return [
        {
            "id": str(ticket.id),
            "run_id": str(ticket.runId),
            "kind": ticket.kind,
            "expires_at": (
                timezone.now()
                + timedelta(seconds=max(0, ticket.expiresAt - time.monotonic()))
            ).isoformat(),
        }
        for ticket in listTicket
        if ticket.sessionId == sessionId
        and ticket.state == TransferState.WAITING
        and not ticket.canceledEvent.is_set()
    ]


@require_POST
def create_file_transfer(request: HttpRequest, runId: uuid.UUID) -> HttpResponse:
    payload = parse_json_request(request, RunFileRequest)
    if isinstance(payload, JsonResponse):
        return payload
    ticket: TransferTicket | None = None
    boolCommitted = False
    try:
        # Cleanup must not roll back with a subsequently rejected admission.
        _expire_tickets()
        with transaction.atomic():
            access = get_request_access(request, forUpdate=True)
            run = get_visible_runs(access).get(pk=runId)
            fileAvailability = build_run_file_availability(run)[payload.kind]
            if not fileAvailability["available"]:
                raise ValidationError(fileAvailability["reason"])
            require_download_slot(access.organization.pk)
            transfer = RunFileTransfer.objects.create(
                organization=access.organization,
                run=run,
                actor_id=access.actorId,
                session_id=run.assignment.session_id,
                kind=payload.kind,
                # Ready extends this lease once; an abandoned preparation expires promptly.
                expires_at=timezone.now() + timedelta(seconds=_INT_PREPARATION_SECONDS),
            )
            ticket = TransferTicket(
                id=transfer.pk,
                organizationId=access.organization.pk,
                actorId=access.actorId,
                sessionId=run.assignment.session_id,
                runId=run.pk,
                kind=payload.kind,
                expiresAt=time.monotonic() + _INT_PREPARATION_SECONDS,
            )

            # The organization lock protects the shared download count and reservation.
            # Publish before the committed notification can wake the source.
            with _LOCK_TICKET:
                _DICT_TICKET[ticket.id] = ticket
            notify_executor_control(run.assignment.executor_id)
            response = JsonResponse({
                "download_url": f"/api/run-files/{transfer.pk}/",
                "expires_at": (
                    timezone.now() + timedelta(seconds=_INT_PREPARATION_SECONDS)
                ).isoformat(),
            })
        boolCommitted = True
        return response
    except (PermissionDenied, ObjectDoesNotExist):
        return build_error_response(
            "run_unavailable", "Run access is unavailable.", statusCode=403
        )
    except ValidationError as e:
        return build_error_response("file_unavailable", e.messages[0], statusCode=409)
    except FileOperationError as e:
        return build_error_response("transfer_capacity", str(e), statusCode=429)
    finally:
        if ticket is not None and not boolCommitted:
            ticket.canceledEvent.set()
            with _LOCK_TICKET:
                _DICT_TICKET.pop(ticket.id, None)


def _authorize_source(authorizationHeader: str, ticket: TransferTicket) -> None:
    authentication = authenticate_resource(authorizationHeader)
    if (
        not isinstance(authentication, NativeResourceAuthenticationContext)
        or authentication.access.channel != AccessChannel.EXECUTOR
    ):
        raise PermissionDenied("The original Executor session is required.")
    with transaction.atomic():
        access = lock_resource_write_access(authentication)
        if (
            authentication.sessionId != ticket.sessionId
            or access.organization.pk != ticket.organizationId
        ):
            raise PermissionDenied("The original Executor session is required.")
        run = get_visible_runs(access).get(pk=ticket.runId)
        if (
            run.assignment.session_id != ticket.sessionId
            or run.assignment.actor_id != access.actorId
            or run.ended_at is None
        ):
            raise PermissionDenied("The original completed Run is required.")


@csrf_exempt
@require_POST
def set_file_ready(request: HttpRequest, transferId: uuid.UUID) -> HttpResponse:
    authentication = authenticate_resource_request(request)
    if isinstance(authentication, JsonResponse):
        return authentication
    payload = parse_json_request(request, FileReadyRequest)
    if isinstance(payload, JsonResponse):
        return payload
    ticket: TransferTicket | None = None
    boolOwnPreparation = False
    boolCommitted = False
    strFailureMessage = "The original file preparation could not be completed."

    def build_ready_response(ticket: TransferTicket) -> JsonResponse:
        return JsonResponse({
            "ready": not bool(ticket.error),
            "transfer_timeout_ms": max(
                0, int((ticket.expiresAt - time.monotonic()) * 1000)
            ),
            "idle_timeout_ms": _INT_IDLE_SECONDS * 1000,
        })

    try:
        ticket = _get_ticket(transferId)
        # Reuse the parsed credential context; only commit-time eligibility is rechecked.
        if (
            not isinstance(authentication, NativeResourceAuthenticationContext)
            or authentication.access.channel != AccessChannel.EXECUTOR
        ):
            raise PermissionDenied
        with transaction.atomic():
            access = lock_resource_write_access(authentication)
            if (
                authentication.sessionId != ticket.sessionId
                or access.organization.pk != ticket.organizationId
            ):
                raise PermissionDenied
            with _LOCK_TICKET:
                if ticket.canceledEvent.is_set() or ticket.expiresAt <= time.monotonic():
                    raise PermissionDenied
                if ticket.state != TransferState.WAITING:
                    if (
                        ticket.sizeBytes == payload.size_bytes
                        and ticket.filename == payload.filename
                        and ticket.error == payload.error
                    ):
                        return build_ready_response(ticket)
                    raise ValidationError(
                        "This transfer was already prepared with different metadata."
                    )
                boolOwnPreparation = True
                if payload.size_bytes > _DICT_MAX_FILE_BYTES[ticket.kind]:
                    raise ValidationError(
                        "This file exceeds the Console download limit; "
                        "retrieve it on the Executor computer."
                    )
                if any(char in payload.filename for char in "\r\n/\\\x00"):
                    raise ValidationError("Invalid download filename.")

            # Extend the existing download slot, never acquire an upload slot for the relay.
            # Do not hold the in-memory lock during database I/O.
            floatExpiresAt = ticket.expiresAt
            if not payload.error:
                currentTime = timezone.now()
                floatExpiresAt = time.monotonic() + _INT_TRANSFER_SECONDS
                intUpdatedCount = RunFileTransfer.objects.filter(
                    pk=ticket.id,
                    organization_id=ticket.organizationId,
                    expires_at__gt=currentTime,
                ).update(
                    expires_at=currentTime + timedelta(seconds=_INT_TRANSFER_SECONDS)
                )
                if not intUpdatedCount:
                    raise PermissionDenied
            with _LOCK_TICKET:
                if ticket.canceledEvent.is_set() or ticket.expiresAt <= time.monotonic():
                    raise PermissionDenied
                ticket.error = payload.error
                ticket.sizeBytes = payload.size_bytes
                ticket.filename = payload.filename
                ticket.contentType = (
                    "application/zip"
                    if ticket.kind == RunFileKind.LOGS
                    else "text/plain; charset=utf-8"
                    if ticket.kind == RunFileKind.SUBTITLES
                    else "application/octet-stream"
                )
                ticket.expiresAt = floatExpiresAt
                ticket.state = TransferState.READY
            # A failed commit must not wake a waiting browser with a successful Ready.
            transaction.on_commit(ticket.readyEvent.set)
            response = build_ready_response(ticket)
        boolCommitted = True
        if ticket.error:
            _discard_ticket(ticket)
        return response
    except (PermissionDenied, ObjectDoesNotExist):
        return build_error_response(
            "transfer_unavailable",
            "The original file transfer is unavailable.",
            statusCode=403,
        )
    except ValidationError as e:
        strFailureMessage = e.messages[0]
        return build_error_response("file_unavailable", strFailureMessage, statusCode=409)
    finally:
        if boolOwnPreparation and not boolCommitted and ticket is not None:
            _cancel_ticket(ticket, strFailureMessage)
            _discard_ticket(ticket)


def _authorize_browser(scope: HTTPScope, ticket: TransferTicket) -> None:
    dictHeader = dict(scope.get("headers", []))
    cookie = SimpleCookie()
    cookie.load(dictHeader.get(b"cookie", b"").decode("latin1"))
    morsel = cookie.get(settings.SESSION_COOKIE_NAME)
    request = HttpRequest()
    request.META["HTTP_HOST"] = dictHeader.get(b"host", b"").decode("latin1")
    request.get_host()
    request.session = SessionStore(session_key=morsel.value if morsel else None)
    request.user = get_user(request)
    access = get_request_access(request)
    if (
        access.actorId != ticket.actorId
        or access.organization.pk != ticket.organizationId
    ):
        raise PermissionDenied
    get_visible_runs(access).get(pk=ticket.runId)


async def _send_error(send: ASGISendCallable, statusCode: int, message: str) -> None:
    content = json.dumps({
        "error": {"code": "file_unavailable", "message": message}
    }).encode()
    await send({
        "type": "http.response.start",
        "status": statusCode,
        "headers": [
            (b"content-type", b"application/json"),
            (b"cache-control", b"no-store"),
        ],
        "trailers": False,
    })
    await send({"type": "http.response.body", "body": content, "more_body": False})


async def _wait_event(event: threading.Event, ticket: TransferTicket) -> None:
    floatDeadline = min(time.monotonic() + _INT_IDLE_SECONDS, ticket.expiresAt)
    while True:
        if ticket.error:
            raise ValueError(ticket.error)
        if ticket.canceledEvent.is_set() or time.monotonic() >= floatDeadline:
            raise TimeoutError("The original Executor did not provide the file in time.")
        if event.is_set():
            return
        await asyncio.to_thread(event.wait, 0.5)


async def _put_chunk(ticket: TransferTicket, content: bytes | None) -> None:
    floatDeadline = min(time.monotonic() + _INT_IDLE_SECONDS, ticket.expiresAt)
    while not ticket.canceledEvent.is_set() and time.monotonic() < floatDeadline:
        try:
            await asyncio.to_thread(ticket.chunks.put, content, True, 1)
            return
        except queue.Full:
            continue
    raise ConnectionError("The browser download stopped accepting data.")


async def _receive_file(
    scope: HTTPScope,
    receive: ASGIReceiveCallable,
    send: ASGISendCallable,
    ticket: TransferTicket,
) -> None:
    dictHeader = dict(scope.get("headers", []))
    await sync_to_async(_authorize_source)(
        dictHeader.get(b"authorization", b"").decode("latin1"), ticket
    )
    if ticket.state != TransferState.READY or ticket.error:
        raise PermissionDenied("The original file was not prepared.")
    ticket.state = TransferState.STREAMING
    try:
        async with asyncio.timeout(max(0, ticket.expiresAt - time.monotonic())):
            await _wait_event(ticket.consumerEvent, ticket)
            intReceivedBytes = 0
            while True:
                message = await asyncio.wait_for(receive(), _INT_IDLE_SECONDS)
                if message["type"] == "http.disconnect":
                    raise ConnectionError(
                        "The Executor disconnected during the transfer."
                    )
                content = message.get("body", b"")
                intReceivedBytes += len(content)
                if intReceivedBytes > ticket.sizeBytes:
                    raise ValueError("The source sent more bytes than declared.")
                for intOffset in range(0, len(content), _INT_CHUNK_BYTES):
                    await _put_chunk(
                        ticket, content[intOffset : intOffset + _INT_CHUNK_BYTES]
                    )
                if not message.get("more_body", False):
                    break
            if intReceivedBytes != ticket.sizeBytes:
                raise ValueError("The source file ended before its declared size.")
            await _put_chunk(ticket, None)
            ticket.state = TransferState.FINISHED
            await asyncio.wait_for(
                send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                    "trailers": False,
                }),
                _INT_IDLE_SECONDS,
            )
            await asyncio.wait_for(
                send({
                    "type": "http.response.body",
                    "body": b'{"received":true}',
                    "more_body": False,
                }),
                _INT_IDLE_SECONDS,
            )
    except (Exception, asyncio.CancelledError) as e:
        # Only this authenticated source owns the stream and may abort its browser consumer.
        _cancel_ticket(ticket, "The original file stream was interrupted.")
        await sync_to_async(_discard_ticket)(ticket)
        if isinstance(e, TimeoutError):
            raise TimeoutError("The original file transfer timed out.") from e
        raise


async def _download_file(
    scope: HTTPScope,
    receive: ASGIReceiveCallable,
    send: ASGISendCallable,
    ticket: TransferTicket,
) -> None:
    async def get_chunk() -> bytes | None:
        floatDeadline = min(time.monotonic() + _INT_IDLE_SECONDS, ticket.expiresAt)
        while not ticket.canceledEvent.is_set() and time.monotonic() < floatDeadline:
            try:
                return await asyncio.to_thread(ticket.chunks.get, True, 1)
            except queue.Empty:
                continue
        raise ConnectionError("The original file stream was interrupted.")

    async def watch_disconnect() -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                _cancel_ticket(ticket, "The browser download was disconnected.")
                return

    await sync_to_async(_authorize_browser)(scope, ticket)
    if ticket.consumerEvent.is_set():
        raise PermissionDenied("The download has already started.")
    taskDisconnect = asyncio.create_task(watch_disconnect())
    boolStarted = False
    try:
        ticket.consumerEvent.set()
        await _wait_event(ticket.readyEvent, ticket)
        if ticket.error:
            raise ValueError(ticket.error)
        async with asyncio.timeout(max(0, ticket.expiresAt - time.monotonic())):
            strDisposition = content_disposition_header(True, ticket.filename)
            await asyncio.wait_for(
                send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", ticket.contentType.encode()),
                        (b"content-length", str(ticket.sizeBytes).encode()),
                        (b"content-disposition", strDisposition.encode("latin1")),
                        (b"cache-control", b"no-store"),
                        (b"x-accel-buffering", b"no"),
                    ],
                    "trailers": False,
                }),
                _INT_IDLE_SECONDS,
            )
            boolStarted = True
            while True:
                content = await get_chunk()
                if content is None:
                    await asyncio.wait_for(
                        send({
                            "type": "http.response.body",
                            "body": b"",
                            "more_body": False,
                        }),
                        _INT_IDLE_SECONDS,
                    )
                    break
                with _LOCK_TICKET:
                    floatStart = max(
                        time.monotonic(), _DICT_RATE_TIME.get(ticket.organizationId, 0)
                    )
                    _DICT_RATE_TIME[ticket.organizationId] = (
                        floatStart + len(content) / _INT_BYTES_PER_SECOND
                    )
                await asyncio.sleep(max(0, floatStart - time.monotonic()))
                await asyncio.wait_for(
                    send({
                        "type": "http.response.body",
                        "body": content,
                        "more_body": True,
                    }),
                    _INT_IDLE_SECONDS,
                )
    except Exception as e:
        if boolStarted:
            # Raising aborts the incomplete Content-Length response instead of claiming a successful file.
            ticket.canceledEvent.set()
        if isinstance(e, TimeoutError):
            raise TimeoutError("The original file transfer timed out.") from e
        raise
    finally:
        taskDisconnect.cancel()
        with suppress(asyncio.CancelledError):
            await taskDisconnect
        await sync_to_async(_discard_ticket)(ticket)


class RunFileRelay:
    """Relay original files before Django's request-body spooling, with bounded memory and backpressure.

    Use one ASGI application process; control and mail workers remain independent processes.
    A restart aborts ephemeral downloads and clients can explicitly request them again.
    """

    def __init__(self, application: ASGI3Application) -> None:
        self.application = application

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        if scope["type"] != "http":
            return await self.application(scope, receive, send)
        strPath = scope.get("path", "")
        downloadMatch = re.fullmatch(r"/api/run-files/([0-9a-f-]{36})/", strPath)
        uploadMatch = re.fullmatch(
            r"/api/clients/executor/file-transfers/([0-9a-f-]{36})/content/", strPath
        )
        match = downloadMatch or uploadMatch
        if match is None:
            return await self.application(scope, receive, send)
        boolStarted = False

        async def record_send(message: ASGISendEvent) -> None:
            nonlocal boolStarted
            if message["type"] == "http.response.start":
                boolStarted = True
            await send(message)

        try:
            ticket = _get_ticket(uuid.UUID(match.group(1)))
            if downloadMatch is not None and scope.get("method") == "GET":
                await _download_file(scope, receive, record_send, ticket)
            elif uploadMatch is not None and scope.get("method") == "PUT":
                await _receive_file(scope, receive, record_send, ticket)
            else:
                await _send_error(record_send, 405, "Unsupported transfer method.")
        except Exception as e:
            # Authorization failures and duplicate opens must not cancel another request's transfer.
            if boolStarted:
                raise
            await _send_error(
                record_send,
                403
                if isinstance(
                    e,
                    (
                        PermissionDenied,
                        ObjectDoesNotExist,
                        InvalidResourceCredentialError,
                        InvalidApiKeyError,
                    ),
                )
                else 409,
                str(e)
                if isinstance(e, (ValueError, TimeoutError, ConnectionError))
                else "The original file or current authorization is unavailable.",
            )
