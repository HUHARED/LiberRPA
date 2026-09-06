# FileName: _ListenerSocketConnect.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketConnect ===")
from liberrpa.Logging import Log

from liberrpa.LiberRPALocalServer._Qt import dictClientAreaCache, close_area
from liberrpa.LiberRPALocalServer._ServerInit import (
    ClientType,
    get_client_id,
    is_server_shutting_down,
    register_client_type,
    remove_client_type,
    sioServer,
)
from liberrpa.Common._BasicConfig import get_local_server_port, get_token

import hmac
from urllib.parse import urlparse
from flask import request
from socketio.exceptions import ConnectionRefusedError as SocketConnectionRefusedError
from typing import cast


SET_ALLOWED_CLIENT_TYPES: set[str] = {"python", "chrome", "uiAnalyzer"}
SET_ALLOWED_UI_ANALYZER_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "file://",
}
SET_ALLOWED_CHROME_EXTENSION_ORIGINS = {
    # NOTE: Without the final "/"
    "chrome-extension://cffobgimbemkfgjmcedebofkfcamnajb",
    "chrome-extension://elnnnehambeohefmcdeiajpodhcdgigb",
    "chrome-extension://cfpkjecgmfmincccpnbheeeojdkooohj",
}


def is_same_local_server_origin(origin: str) -> bool:
    parsed = urlparse(origin)

    if parsed.scheme != "http":
        return False

    if parsed.hostname != "127.0.0.1":
        return False

    return parsed.port == get_local_server_port()


def validate_origin(clientType: ClientType) -> None:
    origin = request.headers.get("Origin")
    Log.debug(f"Socket.IO connect origin: {origin!r}, clientType={clientType}")

    if origin is None:
        return

    if clientType == "python":
        if is_same_local_server_origin(origin):
            return
        raise SocketConnectionRefusedError("origin not allowed")

    if clientType == "chrome":
        if origin in SET_ALLOWED_CHROME_EXTENSION_ORIGINS:
            return
        raise SocketConnectionRefusedError("origin not allowed")

    if clientType == "uiAnalyzer":
        if origin in SET_ALLOWED_UI_ANALYZER_ORIGINS:
            return
        raise SocketConnectionRefusedError("origin not allowed")

    raise SocketConnectionRefusedError("origin not allowed")


@sioServer.on("connect")
def handle_connect(auth: object) -> None:
    if is_server_shutting_down():
        raise SocketConnectionRefusedError("server is shutting down")

    if not isinstance(auth, dict):
        raise SocketConnectionRefusedError("invalid authentication data")

    clientTypeValue = auth.get("clientType")
    token = auth.get("token")

    if (
        not isinstance(clientTypeValue, str)
        or clientTypeValue not in SET_ALLOWED_CLIENT_TYPES
    ):
        raise SocketConnectionRefusedError("unknown client type")

    if not isinstance(token, str):
        raise SocketConnectionRefusedError("unauthorized")

    clientType = cast(ClientType, clientTypeValue)
    validate_origin(clientType)

    tokenExpected = get_token(clientType)
    if not hmac.compare_digest(token, tokenExpected):
        raise SocketConnectionRefusedError("unauthorized")

    clientSid = get_client_id()
    register_client_type(clientSid=clientSid, clientType=clientType)
    Log.info(f"Client connected: sid={clientSid}, clientType={clientType}")


@sioServer.on("disconnect")
def handle_disconnect() -> None:
    clientSid = get_client_id()
    clientType = remove_client_type(clientSid=clientSid)

    Log.info(f"Client disconnected: sid={clientSid}, clientType={clientType!r}")

    # Import locally to avoid coupling listener registration order during module initialization.
    from liberrpa.LiberRPALocalServer._ListenerSocketChrome import (
        disconnect_chrome_client,
    )

    if disconnect_chrome_client(clientSid=clientSid):
        Log.info(f"Remove active Chrome client {clientSid} from clients dictionary.")

    if dictClientAreaCache.get(clientSid):
        Log.info(
            f"The Python client {clientSid} disconnected but it has unclosed ScreenPrint area: dictClientAreaCache={dictClientAreaCache}"
        )
        for item in dictClientAreaCache[clientSid]:
            close_area(screenPrintObj=item)
        del dictClientAreaCache[clientSid]
        Log.info(f"Cleaned dictClientAreaCache={dictClientAreaCache}")


@sioServer.on("connect_error")
def handle_connect_error() -> None:
    Log.error("Client connects error." + get_client_id())
