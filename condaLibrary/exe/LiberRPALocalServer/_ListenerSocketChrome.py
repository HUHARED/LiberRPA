# FileName: _ListenerSocketChrome.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketChrome ===")
from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictSocketResult

from exe.LiberRPALocalServer._ServerInit import sioServer, dictClients, get_client_id


from flask_socketio import emit
import json
import uuid
from typing import Any

# Record the command be responsed or not, when the command sended to Chrome, create a new key-value pair{id:""}, when Chrome send a result with id, update it to {id:result}, and the function _wait_for_response_by_id() check it, if it's value is not "", means the result returned.
dictCommandIdResponsed: dict[str, dict[str, Any] | None] = {}


@Log.trace()
@sioServer.on("chrome_extension_connect")
def handle_chrome_extension_connect(message: dict[str, str]):
    # Save the Chrome extension's sid for send command to it later, call by Chrome extension.
    clientSid = get_client_id()
    Log.info(f"Chrome connection established. {message}, SID: {clientSid}")

    # Save the Chrome extension sid into dictionary.
    dictClients["Chrome"] = clientSid
    Log.info(f"The Chrome clients: {dictClients}")

    # Send confirmation to Chrome.
    emit("message_flask_to_chrome", json.dumps({"commandName": "confirmConnection"}), to=dictClients["Chrome"])


@Log.trace()
@sioServer.on("chrome_command")
def handle_chrome_command(dictCommand: dict[str, Any]) -> DictSocketResult:
    # The entrance for all Chrome functions to execution, call by Chrome.py.

    Log.info(f"Received Chrome command: {dictCommand}, SID: {get_client_id()}")

    strId = str(uuid.uuid4())

    if _check_Chrome_extension():
        # If the Chrome extension is working, send command to it. Wait the result.
        result: DictSocketResult = _wait_for_response_by_id(commandId=strId, dictCommand=dictCommand)
    else:
        result: DictSocketResult = {
            "boolSuccess": False,
            "data": "Can't access Chrome extension, you should install it and turn it on, and make sure Chrome is running.",
        }

    return result


def _check_Chrome_extension() -> bool:
    # Check weather the Chrome extension is connecting before send command.
    if dictClients.get("Chrome") is None:
        return False
    return True


def _wait_for_response_by_id(commandId: str, dictCommand: dict[str, str]) -> DictSocketResult:

    # If dictCommand can't be serizlized, return an error result directly.
    try:
        strTemp = json.dumps({"id": commandId, **dictCommand})
    except Exception as e:
        return {"boolSuccess": False, "data": f"Error when serialize the command {dictCommand}"}

    emit("message_flask_to_chrome", strTemp, to=dictClients["Chrome"])

    dictCommandIdResponsed[commandId] = None
    # Wait the result to be updated by handle_result_from_chrome().
    while dictCommandIdResponsed[commandId] is None:
        continue

    # Pop the data from dictionary. it will not use again.
    dictResult: DictSocketResult = dictCommandIdResponsed.pop(commandId)  # type: ignore - its type is right

    return dictResult


@Log.trace()
@sioServer.on("result_chrome_to_flask")
def handle_result_from_chrome(message: str) -> None:
    # Receive and update result from Chrome.

    Log.info(f"Received result from Chrome extension: {message}, SID: {get_client_id()}")

    # The result from Chrome must have be serialized correctly, so just deserialize it.
    dictResult: dict[str, Any] = json.loads(message)
    strId = dictResult.pop("id", None)
    if strId in dictCommandIdResponsed.keys():
        Log.debug("Update result into dictionary.")
        dictCommandIdResponsed[strId] = dictResult
    else:
        Log.error("The result from Chrome doesn't have id.")
