# FileName: _WebSocket.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._BasicConfig import get_basic_config_dict
from liberrpa.Common._Exception import ChromeError, QtError
from liberrpa.Common._TypedValue import DictSocketResult

import threading
import socketio
from socketio.exceptions import ConnectionError
from typing import Any

SIGN_START_RECORD_VIDEO = "$SIGN-START_RECORD_VIDEO"

# Initialize the socket client.
intPort = int(get_basic_config_dict()["localServerPort"])
sioClient = socketio.Client(logger=False, engineio_logger=False)


@sioClient.event
def connect():
    # log.debug("Connection established")
    pass


@sioClient.event
def disconnect():
    # log.debug("Disconnected from server")
    pass


@sioClient.event
def connect_error(data):
    Log.error("Connection failed: " + str(data))


def send_command(eventName: str, command: dict[str, Any], timeout: int = 10000) -> Any:
    try:
        # Connect to the LiberRPA local server if not connected.
        # Put it in the function instead of outside, due to LiberRPA local server will import the file, and the web socket has not been build at that time.
        if not sioClient.connected:
            sioClient.connect(f"http://localhost:{intPort}", transports=["websocket"])
            # log.debug(f"Connected to server, sid: {sioClient.sid}")
    except ConnectionError as e:
        raise ConnectionError(f"Failed to connect LiberRPA local server: {e}, is the server running?")

    Log.verbose(f"The command sent to LiberRPA local server:{command}")

    eventResponse = threading.Event()
    dictResponseData: dict[str, DictSocketResult] = {}

    def response_handler(data: DictSocketResult):
        Log.verbose(f"Data received from server: {data}")
        dictResponseData["result"] = data
        eventResponse.set()
        if data.get("data") == SIGN_START_RECORD_VIDEO:
            Log.critical(data["data"])

    # Send command to LiberRPA local server or target platform(such as Chrome extension) by LiberRPA local server.
    sioClient.emit(event=eventName, data=command, callback=response_handler)

    # Wait the response. Add 1 more second than the original.
    """ while not eventResponse.is_set():
        continue """
    if not eventResponse.wait(timeout=(timeout + 1000) / 1000):
        raise TimeoutError(
            f"No response received from LiberRPA local server within {timeout / 1000} seconds. Maybe the data is too huge for Web Socket setting?"
        )

    # Process the received response.
    dictResult: DictSocketResult | None = dictResponseData.get("result")
    if dictResult is None:
        raise ValueError("Not get result from LiberRPA local server.")
    elif not dictResult.get("boolSuccess"):
        # Log.error("Error here!")
        strData = dictResult.get("data")
        # Log.debug(eventName)
        # More specific error type.
        if eventName == "chrome_command":
            raise ChromeError(strData)
        elif eventName == "qt_command":
            raise QtError((strData))
        else:
            raise Exception(strData)
    else:
        # dictResult.get("boolSuccess") == True, Return the data from the successful result.
        return dictResult.get("data")


if __name__ == "__main__":
    Log.critical(SIGN_START_RECORD_VIDEO)
