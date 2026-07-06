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
    ],
    async_mode="threading",
)
boolHasRunServer = False

# Dictionary to track connected clients, only "Chrome" now.
dictClients: dict[str, str] = {}


@_flaskApp.route("/verify")
def verify() -> str:
    # Test weather the Flask server is running.
    return "LiberRPA Local Server Verification"


# Create or use existing Flask server.
def _check_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _check_if_liberrpa_server_has_run(port: int) -> bool:
    try:
        response = requests.get(f"http://127.0.0.1:{port}/verify", timeout=2)
        if response.status_code == 200 and response.text == "LiberRPA Local Server Verification":
            return True
    except requests.exceptions.RequestException:
        return False

    return False


def get_client_id() -> str:
    sid = getattr(request, "sid", None)

    if not isinstance(sid, str):
        raise RuntimeError("Failed to get Socket.IO client sid from request.")

    return sid


def create_flask_server(port: int) -> None:
    """Create a new or use a existing Flask server."""
    global boolHasRunServer
    if _check_port_in_use(port=port):
        if _check_if_liberrpa_server_has_run(port=port):
            strMessage = "There is already a LiberRPA Local Server running."
            Log.debug(strMessage)
            show_notification(title="LiberRPA Local Server", message=strMessage, duration=3, wait=True)
            boolHasRunServer = True
        else:
            show_message_box(
                title="Error on start LiberRPA server",
                type="error",
                message=f"Server port({port}) for browser interaction is occupied, maybe you should modify the LiberRPA config file to use another port or closing the program which is using port {port}",
            )

            raise Exception(f"Port {port} is already in use by another application.")
    else:
        try:
            """show_notification(title="LiberRPA Local Server", message="Launch ...", duration=3, wait=False)"""
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
            show_message_box(title="Error on start LiberRPA server", type="error", message=str(get_exception_info(e)))
            raise Exception(f"Failed to start Flask server on port {port}: {str(get_exception_info(e))}")
