# FileName: _WebSocket.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._BasicConfig import get_local_server_port, get_token
from liberrpa.Common._ProtocolValidation import ensure_socket_result
from liberrpa.Common._Exception import ChromeCommandError, ChromeElementNotFoundError, QtError
from liberrpa.Common._TypedValue import DictSocketResult
import liberrpa.UI._CommonValue as _CommonValue

import threading
import socketio
from socketio.exceptions import ConnectionError
from typing import Any

SIGN_START_RECORD_VIDEO = "$SIGN-START_RECORD_VIDEO"

# Initialize the socket client.
_INT_PORT = get_local_server_port()
_STR_TOKEN = get_token("python")
_sioClient = socketio.Client(logger=False, engineio_logger=False)
_LOCK_SOCKET_CLIENT = threading.Lock()

_INT_TIMEOUT_DEFAULT = 10000


@_sioClient.event
def connect() -> None:
    # log.debug("Connection established")
    pass


@_sioClient.event
def disconnect() -> None:
    # log.debug("Disconnected from server")
    pass


@_sioClient.event
def connect_error(data: object) -> None:
    Log.error("Connection failed: " + str(data))


def _normalize_timeout(timeout: object | None) -> int:
    if timeout is None:
        return _INT_TIMEOUT_DEFAULT

    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise ValueError("The argument 'timeout' must be an integer.")

    if timeout < _CommonValue.INT_TIMEOUT_MIN:
        Log.warning(
            f"The argument 'timeout' should be at least {_CommonValue.INT_TIMEOUT_MIN}; "
            f"using {_CommonValue.INT_TIMEOUT_MIN}."
        )
        return _CommonValue.INT_TIMEOUT_MIN

    return timeout


def send_command(eventName: str, command: dict[str, Any], timeout: int | None = None) -> Any:
    # Some commands include "timeout" in the command dictionary instead of passing it as a separate argument.
    # If timeout is passed explicitly, the explicit argument takes priority.
    timeoutFinal = _normalize_timeout(timeout if timeout is not None else command.get("timeout"))

    eventResponse = threading.Event()
    dictResponseData: dict[str, DictSocketResult] = {}

    def response_handler(data: object) -> None:
        result = ensure_socket_result(data, source="LiberRPA Local Server")
        Log.verbose(f"Data received from server: {result}")

        dictResponseData["result"] = result
        eventResponse.set()

        if result["data"] == SIGN_START_RECORD_VIDEO:
            Log.critical(result["data"])

    try:
        # Protect the shared Socket.IO client.
        # Do not keep this lock while waiting for the response, otherwise a slow command would block unrelated commands.
        with _LOCK_SOCKET_CLIENT:
            # Connect to LiberRPA Local Server if not connected.
            # Keep the connection logic inside this function because LiberRPA Local Server may import this module before the WebSocket connection is needed.
            if not _sioClient.connected:
                _sioClient.connect(
                    f"http://127.0.0.1:{_INT_PORT}",
                    transports=["websocket"],
                    auth={
                        "clientType": "python",
                        "token": _STR_TOKEN,
                    },
                )

            Log.verbose(f"The command sent to LiberRPA Local Server: {command}")

            # Send the command to LiberRPA Local Server, or forward it to a target platform
            # such as the Chrome extension through LiberRPA Local Server.
            _sioClient.emit(event=eventName, data=command, callback=response_handler)
    except ConnectionError as e:
        raise ConnectionError(f"Failed to connect to LiberRPA Local Server: {e}. Is the server running?") from e

    timeoutWithGrace = (timeoutFinal + 1000) / 1000

    if not eventResponse.wait(timeout=timeoutWithGrace):
        raise TimeoutError(
            f"No response was received from LiberRPA Local Server within "
            f"{timeoutFinal / 1000} seconds. The server may be busy, the target platform may not be responding, "
            f"or the response data may be too large for the current WebSocket settings."
        )

    # Process the received response.
    dictResult: DictSocketResult | None = dictResponseData.get("result")

    if dictResult is None:
        raise ValueError("Did not receive a result from LiberRPA Local Server.")

    if not dictResult["boolSuccess"]:
        strData = dictResult["data"]

        # More specific error type.
        if eventName == "chrome_command":
            if isinstance(strData, str) and strData.startswith("Not found the target element"):
                raise ChromeElementNotFoundError(strData)
            raise ChromeCommandError(strData)

        if eventName == "qt_command":
            raise QtError(strData)

        raise Exception(strData)

    # dictResult.get("boolSuccess") == True, Return the data from the successful result.
    return dictResult.get("data")


if __name__ == "__main__":
    Log.critical(SIGN_START_RECORD_VIDEO)
