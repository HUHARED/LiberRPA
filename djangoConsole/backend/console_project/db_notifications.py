# FileName: db_notifications.py
import asyncio
import logging
import threading
from collections.abc import Callable
from enum import StrEnum

import psycopg
from django.db import connection

_LOGGER = logging.getLogger("console.db_notifications")
_INT_RECONNECT_SECONDS = 3


class NotificationChannel(StrEnum):
    EXECUTOR_CONTROL = "liberrpa_executor_control"
    BROWSER_EVENTS = "liberrpa_browser_events"


def publish_database_notification(channel: NotificationChannel, payload: str) -> None:
    """PostgreSQL delivers the notification only after the current transaction commits."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT PG_NOTIFY(%s, %s)", [channel, payload])


def _listen_for_notifications(
    channel: NotificationChannel,
    stopEvent: threading.Event,
    eventLoop: asyncio.AbstractEventLoop,
    onNotification: Callable[[str | None], None],
) -> None:
    dictConnection = connection.get_connection_params()
    dictConnection.pop("cursor_factory", None)
    dictConnection.setdefault("application_name", channel.value)
    boolUnavailable = False
    while not stopEvent.is_set():
        try:
            with psycopg.connect(autocommit=True, **dictConnection) as listener:
                listener.execute(f"LISTEN {channel.value}")
                _LOGGER.info(
                    "Database notification listener %s: channel=%s",
                    "reconnected" if boolUnavailable else "connected",
                    channel.value,
                )
                boolUnavailable = False
                # Subscribe before refreshing changes missed during startup or disconnection.
                eventLoop.call_soon_threadsafe(onNotification, None)
                while not stopEvent.is_set():
                    # Wait on the database socket without issuing periodic SQL queries.
                    for notification in listener.notifies(timeout=1):
                        if stopEvent.is_set():
                            return
                        eventLoop.call_soon_threadsafe(
                            onNotification, notification.payload
                        )
        except (psycopg.Error, OSError):
            if not boolUnavailable:
                _LOGGER.warning(
                    "Database notification listener disconnected; reconnecting: channel=%s.",
                    channel.value,
                    exc_info=True,
                )
            boolUnavailable = True
            stopEvent.wait(_INT_RECONNECT_SECONDS)


async def listen_for_database_notifications(
    channel: NotificationChannel,
    onNotification: Callable[[str | None], None],
) -> None:
    """Use one dedicated listener per channel and ASGI process, including on Windows."""
    stopEvent = threading.Event()
    taskListener = asyncio.create_task(
        asyncio.to_thread(
            _listen_for_notifications,
            channel,
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
