# FileName: _ListenerSocketConnect.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketConnect ===")
from liberrpa.Logging import Log

from exe.LiberRPALocalServer._Qt import dictClientAreaCache, close_area
from exe.LiberRPALocalServer._ServerInit import sioServer, dictClients, get_client_id


@sioServer.on("connect")
def handle_connect() -> None:
    Log.info("Client connected: " + get_client_id())


@sioServer.on("disconnect")
def handle_disconnect() -> None:
    clientSid = get_client_id()

    Log.info("Client disconnected: " + clientSid)
    if clientSid == dictClients.get("Chrome"):
        del dictClients["Chrome"]
        Log.info(f"Remove {clientSid} from clients dictionary.")

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
