# FileName: _Queue.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._Exception import QtError

import multiprocessing
import uuid
from typing import Any
import threading
import queue


# Use the same Queues for all processes to use the QtWorker process.
_queueCommand: multiprocessing.Queue = multiprocessing.Queue()
_queueReturn: multiprocessing.Queue = multiprocessing.Queue()

_QT_COMMAND_LOCK = threading.Lock()
_DEFAULT_QT_RESPONSE_TIMEOUT = 30


def send_command_to_qt(
    command: str,
    data: dict[str, Any],
    timeout: float = _DEFAULT_QT_RESPONSE_TIMEOUT,
) -> Any:
    """
    Helper function to send a command and wait for the response.
    It generates a unique requestId so we know which response belongs to us.
    """
    # print("queueCommand", queueCommand)
    # print("queueReturn", queueReturn)

    requestId = str(uuid.uuid4())
    with _QT_COMMAND_LOCK:
        _queueCommand.put({"command": command, "data": data, "requestId": requestId})

        # Wait for the matching response
        while True:
            # blocks until getting something
            try:
                response: dict[str, Any] = _queueReturn.get(timeout=timeout)
            except queue.Empty as e:
                raise QtError(f"QtWorker did not respond within {timeout} seconds. command={command!r}") from e

            if response.get("requestId") != requestId:
                continue
            if response.get("error"):
                raise QtError(response["error"])

            if response["result"] == "OK":
                return None

            return response["result"]
