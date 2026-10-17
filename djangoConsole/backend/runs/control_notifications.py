# FileName: control_notifications.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid
from collections.abc import Callable

from console_project.db_notifications import (
    NotificationChannel,
    publish_database_notification,
    listen_for_database_notifications,
)

_LOGGER = logging.getLogger("console.runs.control_notifications")


def notify_executor_control(executorId: uuid.UUID) -> None:
    """Wake the Executor only after the caller's current transaction commits."""
    publish_database_notification(NotificationChannel.EXECUTOR_CONTROL, str(executorId))


async def listen_for_executor_notifications(
    onNotification: Callable[[uuid.UUID | None], None],
) -> None:
    def handle_notification(payload: str | None) -> None:
        if payload is None:
            onNotification(None)
            return
        try:
            executorId = uuid.UUID(payload)
        except ValueError:
            _LOGGER.warning("Ignored an invalid Executor control notification.")
            return
        onNotification(executorId)

    await listen_for_database_notifications(
        NotificationChannel.EXECUTOR_CONTROL, handle_notification
    )
