# FileName: executor_socket.py
import asyncio
import json
import logging
import uuid
from contextlib import suppress
from enum import StrEnum
from typing import Literal, cast

from asgiref.sync import sync_to_async
from asgiref.typing import (
    ASGI3Application,
    ASGIReceiveCallable,
    ASGIReceiveEvent,
    ASGISendCallable,
    Scope,
    WebSocketAcceptEvent,
    WebSocketCloseEvent,
    WebSocketScope,
    WebSocketSendEvent,
)
from django.core.exceptions import (
    DisallowedHost,
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, close_old_connections
from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_variables
from pydantic import Field, SecretStr

from accounts.rate_limits import apply_executor_client_rate_limit
from console_project.http import build_error_response, build_rate_limited_response
from executors.client_sessions import (
    InvalidExecutorSessionError,
    ExecutorClientAction,
    get_executor_session_identity,
    open_executor_client_request,
)
from executors.payloads import build_client_session_payload
from executors.models import Executor

from .contracts import WorkSyncRequest
from .control_notifications import listen_for_executor_notifications
from .executor_state import update_executor_work_state

_LOGGER = logging.getLogger("console.runs.control")
_STR_CONTROL_PATH = "/api/clients/executor/control/"
_INT_MAX_MESSAGE_BYTES = 64 * 1024
_INT_AUTHENTICATION_TIMEOUT_SECONDS = 10
_INT_CONTACT_TIMEOUT_SECONDS = 45
_INT_ACCOUNT_REFRESH_HEARTBEATS = 4


class ControlMessageType(StrEnum):
    AUTHENTICATE = "authenticate"
    HEARTBEAT = "heartbeat"
    STATE = "state"
    READY = "ready"
    WORK_AVAILABLE = "work_available"
    ERROR = "error"


class ControlAuthenticationRequest(WorkSyncRequest):
    type: Literal[ControlMessageType.AUTHENTICATE]
    token: SecretStr = Field(max_length=128)


class ControlStateRequest(WorkSyncRequest):
    type: Literal[ControlMessageType.HEARTBEAT, ControlMessageType.STATE]


async def _send_payload(send: ASGISendCallable, payload: dict[str, object]) -> None:
    event: WebSocketSendEvent = {
        "type": "websocket.send",
        "text": json.dumps(payload, cls=DjangoJSONEncoder, separators=(",", ":")),
        "bytes": None,
    }
    await send(event)


async def _close_connection(send: ASGISendCallable, code: int) -> None:
    event: WebSocketCloseEvent = {"type": "websocket.close", "code": code, "reason": ""}
    await send(event)


async def _send_error(
    send: ASGISendCallable, response: JsonResponse, executorId: uuid.UUID | None
) -> None:
    dictError = json.loads(response.content)["error"]
    dictPayload: dict[str, object] = {
        "type": ControlMessageType.ERROR,
        "status": response.status_code,
        "code": dictError["code"],
        "message": dictError["message"],
    }
    if response.has_header("Retry-After"):
        dictPayload["retry_after"] = int(response["Retry-After"])
    intCloseCode = (
        1013 if response.status_code in (429, 503) else 4000 + response.status_code
    )
    _LOGGER.warning(
        "Executor control ended: executor=%s, error=%s (requested close code=%s).",
        executorId,
        dictError["code"],
        intCloseCode,
    )
    await _send_payload(send, dictPayload)
    await _close_connection(send, intCloseCode)


def _parse_message[Request: WorkSyncRequest](
    event: ASGIReceiveEvent, requestClass: type[Request]
) -> Request | JsonResponse | None:
    if event["type"] == "websocket.disconnect":
        return None
    if event["type"] != "websocket.receive" or event.get("text") is None:
        return build_error_response(
            "invalid_control_message", "Send a JSON text message.", statusCode=400
        )
    strMessage = event.get("text") or ""
    try:
        if len(strMessage.encode("utf-8")) > _INT_MAX_MESSAGE_BYTES:
            return build_error_response(
                "request_too_large", "The control message is too large.", statusCode=413
            )
        return requestClass.model_validate_json(strMessage)
    except (ValueError, RecursionError):
        return build_error_response(
            "invalid_control_message",
            "Send the required control fields with valid types and no unknown fields.",
            statusCode=400,
        )


@sensitive_variables()
def _process_message(
    clientAddress: str,
    token: SecretStr,
    payload: ControlAuthenticationRequest | ControlStateRequest,
    *,
    refreshAccount: bool = False,
) -> tuple[uuid.UUID, dict[str, object]] | JsonResponse:
    # Long-lived ASGI connections do not run Django's HTTP connection cleanup hooks.
    close_old_connections()
    try:
        intRetryAfter = apply_executor_client_rate_limit(clientAddress)
        if intRetryAfter:
            return build_rate_limited_response(intRetryAfter)
        with open_executor_client_request(
            identity=get_executor_session_identity(f"Bearer {token.get_secret_value()}"),
            action=ExecutorClientAction.HEARTBEAT,
        ) as authentication:
            if authentication is None:
                raise InvalidExecutorSessionError("A valid Executor session is required.")
            session = authentication.session
            executorId = session.executor_id
            if executorId is None:
                raise InvalidExecutorSessionError("Select an Executor first.")
            update_executor_work_state(session, payload)
            if payload.type == ControlMessageType.STATE:
                dictPayload: dict[str, object] = {"type": ControlMessageType.STATE}
            elif payload.type == ControlMessageType.AUTHENTICATE:
                dictPayload = {
                    "type": ControlMessageType.READY,
                    **build_client_session_payload(session, authentication.access),
                }
            else:
                executor = cast(Executor, session.executor)
                dictPayload = {
                    "type": ControlMessageType.HEARTBEAT,
                    "session_id": session.id,
                    "executor_id": executorId,
                    "expires_at": session.expires_at,
                    "last_seen_at": session.last_seen_at,
                    "dispatch_enabled": executor.dispatch_enabled,
                    "account": build_client_session_payload(
                        session, authentication.access
                    )
                    if refreshAccount
                    else None,
                }
            return executorId, dictPayload
    except InvalidExecutorSessionError:
        return build_error_response(
            "executor_authentication_required",
            "A valid original Executor association is required.",
            statusCode=401,
        )
    except PermissionDenied:
        return build_error_response(
            "organization_access_required",
            "Organization business access is unavailable.",
            statusCode=403,
        )
    except ValidationError as e:
        return build_error_response(
            getattr(e, "code", None) or "invalid_executor_control",
            "; ".join(e.messages),
            statusCode=409,
        )
    except (DatabaseError, ImproperlyConfigured):
        _LOGGER.exception("Executor control contact could not commit.")
        return build_error_response(
            "service_unavailable",
            "The service is temporarily unavailable.",
            statusCode=503,
        )
    finally:
        close_old_connections()


class ExecutorControl:
    """Own WebSocket connections and one PostgreSQL notification listener per ASGI process."""

    def __init__(self, application: ASGI3Application) -> None:
        self.application = application
        self.connections: dict[uuid.UUID, set[asyncio.Event]] = {}
        self.listenerTask: asyncio.Task[None] | None = None

    def _notify_connections(self, executorId: uuid.UUID | None) -> None:
        listWakeup = (
            [event for events in self.connections.values() for event in events]
            if executorId is None
            else list(self.connections.get(executorId, ()))
        )
        for wakeupEvent in listWakeup:
            # Several changes can share one request to refresh the work state.
            wakeupEvent.set()

    async def _handle_lifespan(
        self, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        while True:
            event = await receive()
            if event["type"] == "lifespan.startup":
                self.listenerTask = asyncio.create_task(
                    listen_for_executor_notifications(self._notify_connections)
                )
                await send({"type": "lifespan.startup.complete"})
            elif event["type"] == "lifespan.shutdown":
                if self.listenerTask is not None:
                    self.listenerTask.cancel()
                    with suppress(asyncio.CancelledError):
                        await self.listenerTask
                    self.listenerTask = None
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _handle_connection(
        self,
        scope: WebSocketScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> None:
        event = await receive()
        if event["type"] != "websocket.connect":
            return
        if scope["path"] != _STR_CONTROL_PATH:
            await _close_connection(send, 1008)
            return
        request = HttpRequest()
        request.META["HTTP_HOST"] = next(
            (
                value.decode("latin-1")
                for name, value in scope["headers"]
                if name.lower() == b"host"
            ),
            "",
        )
        try:
            request.get_host()
        except DisallowedHost:
            await _close_connection(send, 1008)
            return
        acceptEvent: WebSocketAcceptEvent = {
            "type": "websocket.accept",
            "subprotocol": None,
            "headers": [],
        }
        await send(acceptEvent)
        executorId: uuid.UUID | None = None
        wakeupEvent = asyncio.Event()
        receiveTask: asyncio.Future[ASGIReceiveEvent] | None = None
        wakeupTask: asyncio.Task[bool] | None = None
        try:
            event = await asyncio.wait_for(
                receive(), timeout=_INT_AUTHENTICATION_TIMEOUT_SECONDS
            )
            payload = _parse_message(event, ControlAuthenticationRequest)
            if payload is None:
                return
            if isinstance(payload, JsonResponse):
                await _send_error(send, payload, executorId)
                return
            client = scope.get("client")
            strClientAddress = client[0] if client is not None else ""
            result = await sync_to_async(_process_message, thread_sensitive=False)(
                strClientAddress, payload.token, payload
            )
            if isinstance(result, JsonResponse):
                await _send_error(send, result, executorId)
                return
            executorId, dictResponse = result
            self.connections.setdefault(executorId, set()).add(wakeupEvent)
            await _send_payload(send, dictResponse)
            _LOGGER.info("Executor control connected: executor=%s", executorId)
            loop = asyncio.get_running_loop()
            floatDeadline = loop.time() + _INT_CONTACT_TIMEOUT_SECONDS
            intHeartbeatCount = 0
            receiveTask = asyncio.ensure_future(receive())
            wakeupTask = asyncio.create_task(wakeupEvent.wait())
            while True:
                setDone, _ = await asyncio.wait(
                    (receiveTask, wakeupTask),
                    timeout=max(0, floatDeadline - loop.time()),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not setDone:
                    raise TimeoutError
                if receiveTask in setDone:
                    event = receiveTask.result()
                    statePayload = _parse_message(event, ControlStateRequest)
                    if statePayload is None:
                        return
                    if isinstance(statePayload, JsonResponse):
                        await _send_error(send, statePayload, executorId)
                        return
                    if statePayload.type == ControlMessageType.HEARTBEAT:
                        intHeartbeatCount += 1
                    # Display details refresh every four heartbeats; every contact still authenticates.
                    boolRefreshAccount = (
                        intHeartbeatCount == _INT_ACCOUNT_REFRESH_HEARTBEATS
                    )
                    result = await sync_to_async(
                        _process_message, thread_sensitive=False
                    )(
                        strClientAddress,
                        payload.token,
                        statePayload,
                        refreshAccount=boolRefreshAccount,
                    )
                    if isinstance(result, JsonResponse):
                        await _send_error(send, result, executorId)
                        return
                    if boolRefreshAccount:
                        intHeartbeatCount = 0
                    _, dictResponse = result
                    await _send_payload(send, dictResponse)
                    floatDeadline = loop.time() + _INT_CONTACT_TIMEOUT_SECONDS
                    receiveTask = asyncio.ensure_future(receive())
                if wakeupTask in setDone:
                    wakeupEvent.clear()
                    await _send_payload(send, {"type": ControlMessageType.WORK_AVAILABLE})
                    wakeupTask = asyncio.create_task(wakeupEvent.wait())
        except TimeoutError:
            await _send_error(
                send,
                build_error_response(
                    "control_timeout", "The control connection timed out.", statusCode=408
                ),
                executorId,
            )
        finally:
            for pendingTask in (receiveTask, wakeupTask):
                if pendingTask is not None:
                    pendingTask.cancel()
                    with suppress(asyncio.CancelledError):
                        await pendingTask
            if executorId is not None:
                connections = self.connections.get(executorId)
                if connections is not None:
                    connections.discard(wakeupEvent)
                    if not connections:
                        self.connections.pop(executorId, None)
            if event["type"] == "websocket.disconnect":
                intCloseCode = event["code"]
                _LOGGER.log(
                    logging.INFO if intCloseCode in (1000, 1001) else logging.WARNING,
                    "Executor control disconnected: executor=%s (close code=%s).",
                    executorId,
                    intCloseCode,
                )

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        elif scope["type"] == "websocket":
            try:
                await self._handle_connection(scope, receive, send)
            except OSError:
                # A transport may close before the application receives its disconnect event.
                _LOGGER.warning("Executor control connection was interrupted.")
        else:
            await self.application(scope, receive, send)
