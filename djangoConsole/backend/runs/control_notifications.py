# FileName: control_notifications.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import asyncio
import logging
import threading
import uuid
from collections.abc import Callable

import psycopg
from django.db import connection

_LOGGER = logging.getLogger("console.runs.control_notifications")
_STR_NOTIFICATION_CHANNEL = "liberrpa_executor_control"
_INT_RECONNECT_SECONDS = 3


def notify_executor_control(executorId: uuid.UUID) -> None:
    """Wake the Executor only after the caller's current transaction commits."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_notify(%s, %s)",
            [_STR_NOTIFICATION_CHANNEL, str(executorId)],
        )


def _listen_for_notifications(
    stopEvent: threading.Event,
    eventLoop: asyncio.AbstractEventLoop,
    onNotification: Callable[[uuid.UUID | None], None],
) -> None:
    dictConnection = connection.get_connection_params()
    # The dedicated listener uses psycopg directly, without Django's cursor wrapper.
    dictConnection.pop("cursor_factory", None)
    dictConnection.setdefault("application_name", "liberrpa_executor_control")
    boolUnavailable = False
    while not stopEvent.is_set():
        try:
            with psycopg.connect(autocommit=True, **dictConnection) as listener:
                listener.execute(f"LISTEN {_STR_NOTIFICATION_CHANNEL}")
                if boolUnavailable:
                    _LOGGER.info("Executor control notification listener reconnected.")
                else:
                    _LOGGER.info("Executor control notification listener connected.")
                boolUnavailable = False
                # LISTEN is active before clients reconcile state missed during a disconnect.
                eventLoop.call_soon_threadsafe(onNotification, None)
                while not stopEvent.is_set():
                    # This waits on the database socket; it does not issue periodic SQL queries.
                    for notification in listener.notifies(timeout=1):
                        if stopEvent.is_set():
                            return
                        try:
                            executorId = uuid.UUID(notification.payload)
                        except ValueError:
                            _LOGGER.warning(
                                "Ignored an invalid Executor control notification."
                            )
                            continue
                        eventLoop.call_soon_threadsafe(onNotification, executorId)
        except (psycopg.Error, OSError) as e:
            if not boolUnavailable:
                _LOGGER.warning(
                    "Executor control notification listener disconnected; reconnecting: %s",
                    type(e).__name__,
                )
            boolUnavailable = True
            stopEvent.wait(_INT_RECONNECT_SECONDS)


async def listen_for_executor_notifications(
    onNotification: Callable[[uuid.UUID | None], None],
) -> None:
    """Keep one PostgreSQL listener per ASGI process, including Windows event loops."""
    stopEvent = threading.Event()
    taskListener = asyncio.create_task(
        asyncio.to_thread(
            _listen_for_notifications,
            stopEvent,
            asyncio.get_running_loop(),
            onNotification,
        )
    )
    try:
        await asyncio.shield(taskListener)
    finally:
        stopEvent.set()
        await taskListener
