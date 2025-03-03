# FileName: _Queue.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._Exception import QtError

import multiprocessing
import uuid
from typing import Any


# Use the same Queues for all processes to use the QtWorker process.
queueCommand: multiprocessing.Queue = multiprocessing.Queue()
queueReturn: multiprocessing.Queue = multiprocessing.Queue()


def send_command_to_qt(command: str, data: dict[str, Any]) -> Any:
    """
    Helper function to send a command and wait for the response.
    It generates a unique requestId so we know which response belongs to us.
    """
    # print("queueCommand", queueCommand)
    # print("queueReturn", queueReturn)

    requestId = str(uuid.uuid4())
    queueCommand.put({"command": command, "data": data, "requestId": requestId})
    # print("queueCommand.put")

    # Wait for the matching response
    while True:
        # blocks until getting something
        response: dict[str, Any] = queueReturn.get()
        # print(response)
        if response.get("requestId") == requestId:
            # print("Get response.")
            if response.get("error"):
                raise QtError(response["error"])

            if response["result"] == "OK":
                return None

            return response["result"]
