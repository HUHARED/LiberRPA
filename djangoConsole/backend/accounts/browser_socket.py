# FileName: browser_socket.py
import asyncio
import json
import logging
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit
from typing import cast

from asgiref.sync import sync_to_async
from asgiref.typing import (
    ASGI3Application,
    ASGIReceiveCallable,
    ASGIReceiveEvent,
    ASGISendCallable,
    Scope,
    WebSocketScope,
)
from django.conf import settings
from django.contrib.auth import get_user
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import DisallowedHost, ImproperlyConfigured
from django.db import DatabaseError, close_old_connections
from django.http import HttpRequest
from django.http.cookie import parse_cookie
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.db_notifications import (
    NotificationChannel,
    listen_for_database_notifications,
)

from .contracts import BrowserMessageType
from .models import User

_LOGGER = logging.getLogger("console.accounts.browser_socket")
_STR_BROWSER_PATH = "/api/browser/events/"
_SET_CHANGE_MESSAGE = frozenset({
    BrowserMessageType.SESSION_CHANGED,
    BrowserMessageType.NOTIFICATIONS_CHANGED,
    BrowserMessageType.EXECUTION_CHANGED,
})

type _BrowserChange = tuple[BrowserMessageType, uuid.UUID | None]


@dataclass(frozen=True)
class BrowserSession:
    userId: uuid.UUID
    expiresAt: datetime


def _has_browser_origin(scope: WebSocketScope) -> bool:
    dictHeader = {
        name.lower(): value.decode("latin-1") for name, value in scope["headers"]
    }
    request = HttpRequest()
    request.META["HTTP_HOST"] = dictHeader.get(b"host", "")
    try:
        strHost = request.get_host()
    except DisallowedHost:
        return False
    # The configured public scheme also covers TLS terminated by the reverse proxy.
    strScheme = urlsplit(settings.CONSOLE_URL).scheme
    return dictHeader.get(b"origin") == f"{strScheme}://{strHost}"


@sensitive_variables()
def _load_browser_session(sessionKey: str | None) -> BrowserSession | None:
    close_old_connections()
    try:
        request = HttpRequest()
        request.session = SessionStore(session_key=sessionKey)
        user = get_user(request)
        if not user.is_authenticated:
            return None
        return BrowserSession(
            userId=cast(User, user).pk,
            expiresAt=request.session.get_expiry_date(),
        )
    finally:
        close_old_connections()


async def _send_message(
    send: ASGISendCallable, message: BrowserMessageType, jobId: uuid.UUID | None = None
) -> None:
    dictPayload: dict[str, str | None] = {"type": message}
    if message == BrowserMessageType.EXECUTION_CHANGED:
        dictPayload["job_id"] = str(jobId) if jobId is not None else None
    await send({
        "type": "websocket.send",
        "text": json.dumps(dictPayload, separators=(",", ":")),
        "bytes": None,
    })


async def _close_connection(send: ASGISendCallable, code: int, reason: str) -> None:
    with suppress(OSError):
        await send({"type": "websocket.close", "code": code, "reason": ""})
    _LOGGER.log(
        logging.INFO if code == 4401 else logging.WARNING,
        "Browser push ended: %s (requested close code=%s).",
        reason,
        code,
    )


class BrowserSocket:
    """Share one browser connection between session, notification and execution invalidations."""

    def __init__(self, application: ASGI3Application) -> None:
        self.application = application
        self.connections: dict[uuid.UUID, dict[asyncio.Event, set[_BrowserChange]]] = {}

    def _notify_connections(self, payload: str | None) -> None:
        if payload is None:
            for subscriptions in self.connections.values():
                for wakeup, pending in subscriptions.items():
                    pending.update((message, None) for message in _SET_CHANGE_MESSAGE)
                    wakeup.set()
            return
        try:
            listPart = payload.split(":")
            if len(listPart) not in (2, 3):
                raise ValueError
            message = BrowserMessageType(listPart[0])
            userId = uuid.UUID(listPart[1])
            if message not in _SET_CHANGE_MESSAGE:
                raise ValueError
            if message == BrowserMessageType.EXECUTION_CHANGED:
                if len(listPart) != 3:
                    raise ValueError
                jobId = uuid.UUID(listPart[2])
            else:
                if len(listPart) != 2:
                    raise ValueError
                jobId = None
        except ValueError:
            _LOGGER.warning("Ignored an invalid browser notification.")
            return
        for wakeup, pending in self.connections.get(userId, {}).items():
            pending.add((message, jobId))
            wakeup.set()

    async def _handle_lifespan(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        listenerTask: asyncio.Task[None] | None = None

        async def receive_lifespan() -> ASGIReceiveEvent:
            nonlocal listenerTask
            event = await receive()
            if event["type"] == "lifespan.startup":
                listenerTask = asyncio.create_task(
                    listen_for_database_notifications(
                        NotificationChannel.BROWSER_EVENTS, self._notify_connections
                    )
                )
            elif event["type"] == "lifespan.shutdown" and listenerTask is not None:
                listenerTask.cancel()
                with suppress(asyncio.CancelledError):
                    await listenerTask
                listenerTask = None
            return event

        try:
            await self.application(scope, receive_lifespan, send)
        finally:
            if listenerTask is not None:
                listenerTask.cancel()
                with suppress(asyncio.CancelledError):
                    await listenerTask

    async def _handle_connection(
        self,
        scope: WebSocketScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> None:
        if (await receive())["type"] != "websocket.connect":
            return
        if not _has_browser_origin(scope):
            await _close_connection(send, 1008, "Origin or host was rejected")
            return
        strCookie = next(
            (
                value.decode("latin-1")
                for name, value in scope["headers"]
                if name.lower() == b"cookie"
            ),
            "",
        )
        strSessionKey = parse_cookie(strCookie).get(settings.SESSION_COOKIE_NAME)
        await send({"type": "websocket.accept", "subprotocol": None, "headers": []})
        session = await sync_to_async(_load_browser_session, thread_sensitive=False)(
            strSessionKey
        )
        if session is None:
            await _send_message(send, BrowserMessageType.SESSION_CHANGED)
            await _close_connection(send, 4401, "The session is invalid or expired")
            return

        wakeup = asyncio.Event()
        setPending: set[_BrowserChange] = set()
        self.connections.setdefault(session.userId, {})[wakeup] = setPending
        receiveTask: asyncio.Future[ASGIReceiveEvent] | None = None
        wakeupTask: asyncio.Task[bool] | None = None
        try:
            await _send_message(send, BrowserMessageType.READY)
            receiveTask = asyncio.ensure_future(receive())
            wakeupTask = asyncio.create_task(wakeup.wait())
            while True:
                floatExpiresIn = (session.expiresAt - timezone.now()).total_seconds()
                if floatExpiresIn <= 0:
                    await _send_message(send, BrowserMessageType.SESSION_CHANGED)
                    await _close_connection(send, 4401, "The session expired")
                    return
                setDone, _ = await asyncio.wait(
                    (receiveTask, wakeupTask),
                    timeout=floatExpiresIn,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if receiveTask in setDone:
                    event = receiveTask.result()
                    if event["type"] == "websocket.disconnect":
                        intCode = event["code"]
                        _LOGGER.log(
                            logging.INFO if intCode in (1000, 1001) else logging.WARNING,
                            "Browser push disconnected (close code=%s).",
                            intCode,
                        )
                        return
                    # Protocol keepalive is handled by Uvicorn, not application messages.
                    await _close_connection(send, 1008, "Unexpected application data")
                    return
                if wakeupTask in setDone:
                    wakeup.clear()
                    setMessage = setPending.copy()
                    setPending.clear()
                    refreshed = await sync_to_async(
                        _load_browser_session, thread_sensitive=False
                    )(strSessionKey)
                    if refreshed is None or refreshed.userId != session.userId:
                        await _send_message(send, BrowserMessageType.SESSION_CHANGED)
                        await _close_connection(
                            send, 4401, "The session is no longer valid"
                        )
                        return
                    session = refreshed
                    for message, jobId in sorted(
                        setMessage, key=lambda change: (change[0], str(change[1] or ""))
                    ):
                        await _send_message(send, message, jobId)
                    wakeupTask = asyncio.create_task(wakeup.wait())
        finally:
            for task in (receiveTask, wakeupTask):
                if task is not None:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
            subscriptions = self.connections[session.userId]
            subscriptions.pop(wakeup, None)
            if not subscriptions:
                self.connections.pop(session.userId, None)

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        elif scope["type"] == "websocket" and scope["path"] == _STR_BROWSER_PATH:
            try:
                await self._handle_connection(scope, receive, send)
            except (DatabaseError, ImproperlyConfigured):
                await _close_connection(send, 1013, "Session validation is unavailable")
            except OSError:
                _LOGGER.warning("Browser push connection was interrupted.")
        else:
            await self.application(scope, receive, send)
