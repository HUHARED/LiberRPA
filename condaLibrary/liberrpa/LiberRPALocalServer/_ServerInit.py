# FileName: _ServerInit.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ServerInit ===")
from liberrpa.Logging import Log
from liberrpa.Dialog import show_message_box, show_notification
from liberrpa.Common._Exception import get_exception_info
from liberrpa.Common._BasicConfig import get_local_server_port

from flask import Flask, request
from flask_socketio import SocketIO
import socket
import requests
from threading import Event, Lock
from typing import Literal


_flaskApp = Flask(__name__)
_INT_PORT = get_local_server_port()
sioServer = SocketIO(
    _flaskApp,
    cors_allowed_origins=[
        f"http://127.0.0.1:{_INT_PORT}",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "file://",
        "chrome-extension://cffobgimbemkfgjmcedebofkfcamnajb",
        "chrome-extension://elnnnehambeohefmcdeiajpodhcdgigb",
        "chrome-extension://cfpkjecgmfmincccpnbheeeojdkooohj",
    ],
    async_mode="threading",
    # Debuggers can pause a Python client for a long time. Keep the connection alive so Local Server does not incorrectly clean that client's ScreenPrint objects while execution is suspended.
    ping_timeout=3600,
)


# Track the active Chrome extension connection used for subsequent Chrome commands.
dictClients: dict[str, str] = {}

ClientType = Literal["python", "chrome", "uiAnalyzer"]

# Socket.IO handlers run in different threads. Keep authenticated client identities behind a small locked API.
_lockClientTypeBySid = Lock()
_dictClientTypeBySid: dict[str, ClientType] = {}
_eventServerShutdown = Event()


@_flaskApp.route("/verify")
def verify() -> str:
    # Test whether the Flask server is running.
    return "LiberRPA Local Server Verification"


def _check_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socketObj:
        return socketObj.connect_ex(("127.0.0.1", port)) == 0


def _check_if_liberrpa_server_has_run(port: int) -> bool:
    try:
        response = requests.get(f"http://127.0.0.1:{port}/verify", timeout=2)
        if (
            response.status_code == 200
            and response.text == "LiberRPA Local Server Verification"
        ):
            return True
    except requests.exceptions.RequestException:
        return False

    return False


def begin_server_shutdown() -> None:
    _eventServerShutdown.set()


def is_server_shutting_down() -> bool:
    return _eventServerShutdown.is_set()


def get_client_id() -> str:
    sid = getattr(request, "sid", None)

    if not isinstance(sid, str):
        raise RuntimeError("Failed to get Socket.IO client sid from request.")

    return sid


def register_client_type(*, clientSid: str, clientType: ClientType) -> None:
    with _lockClientTypeBySid:
        existingClientType = _dictClientTypeBySid.get(clientSid)
        if existingClientType is not None and existingClientType != clientType:
            raise RuntimeError(
                f"Socket.IO client {clientSid!r} is already registered as {existingClientType!r}."
            )

        _dictClientTypeBySid[clientSid] = clientType


def remove_client_type(*, clientSid: str) -> ClientType | None:
    with _lockClientTypeBySid:
        return _dictClientTypeBySid.pop(clientSid, None)


def ensure_client_type(
    *, expectedClientType: ClientType, clientSid: str | None = None
) -> None:
    if is_server_shutting_down():
        raise PermissionError("LiberRPA Local Server is shutting down.")

    clientSid = get_client_id() if clientSid is None else clientSid

    with _lockClientTypeBySid:
        actualClientType = _dictClientTypeBySid.get(clientSid)

    if actualClientType is None:
        raise PermissionError(f"Socket.IO client {clientSid!r} is not authenticated.")

    if actualClientType != expectedClientType:
        raise PermissionError(
            f"Socket.IO event requires client type {expectedClientType!r}, "
            f"but client {clientSid!r} is registered as {actualClientType!r}."
        )


def should_start_flask_server(port: int) -> bool:
    """Return whether this process should start a new LiberRPA Local Server."""
    if not _check_port_in_use(port=port):
        return True

    if _check_if_liberrpa_server_has_run(port=port):
        strMessage = "There is already a LiberRPA Local Server running."
        Log.debug(strMessage)
        show_notification(
            title="LiberRPA Local Server",
            message=strMessage,
            duration=3,
            wait=True,
        )
        return False

    show_message_box(
        title="Failed to start LiberRPA Local Server",
        type="error",
        message=(
            f"Server port ({port}) for browser interaction is occupied. "
            "Close the application using this port or configure LiberRPA to use another port."
        ),
    )
    raise RuntimeError(f"Port {port} is already in use by another application.")


def create_flask_server(port: int) -> None:
    """Run the configured Flask-SocketIO server until the process exits."""
    try:
        sioServer.run(
            _flaskApp,
            debug=False,
            host="127.0.0.1",
            port=port,
            use_reloader=False,
            log_output=True,
            allow_unsafe_werkzeug=True,
        )

    except Exception as e:
        strError = str(get_exception_info(e))
        show_message_box(
            title="Failed to start LiberRPA Local Server",
            type="error",
            message=strError,
        )
        raise RuntimeError(
            f"Failed to start Flask server on port {port}: {strError}"
        ) from e
