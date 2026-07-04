# FileName: _ListenerSocketChrome.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketChrome ===")
from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictSocketResult

from liberrpa.LiberRPALocalServer._ServerInit import sioServer, dictClients, get_client_id


from flask_socketio import emit
import json
import uuid
from time import sleep, monotonic
from typing import Any, cast

# Chrome commands use milliseconds for business timeouts.
# This listener timeout is only a communication fallback.
# It should be slightly longer than the Chrome-side timeout, so Chrome can return its own timeout result first.
_DEFAULT_CHROME_COMMAND_TIMEOUT_MS = 15000
_CHROME_RESPONSE_GRACE_MS = 3000

# Record the command be responded or not, when the command sent to Chrome, create a new key-value pair{id:""}, when Chrome send a result with id, update it to {id:result}, and the function _wait_for_response_by_id() check it, if it's value is not "", means the result returned.
_dictPendingChromeCommands: dict[str, dict[str, Any] | None] = {}


@Log.trace()
@sioServer.on("chrome_extension_connect")
def handle_chrome_extension_connect(message: dict[str, str]) -> None:
    # Save the Chrome extension's sid for send command to it later, call by Chrome extension.
    clientSid = get_client_id()
    Log.info(f"Chrome connection established. {message}, SID: {clientSid}")

    # Save the Chrome extension sid into dictionary.
    dictClients["Chrome"] = clientSid
    Log.info(f"The Chrome clients: {dictClients}")


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


def _get_chrome_response_timeout_ms(dictCommand: dict[str, Any]) -> int:
    timeout = dictCommand.get("timeout")
    # timeout should only be int, but adding float in case.
    if isinstance(timeout, (int, float)) and timeout > 0:
        return int(timeout) + _CHROME_RESPONSE_GRACE_MS
    return _DEFAULT_CHROME_COMMAND_TIMEOUT_MS + _CHROME_RESPONSE_GRACE_MS


def _wait_for_response_by_id(commandId: str, dictCommand: dict[str, Any]) -> DictSocketResult:

    # If dictCommand can't be serialized, return an error result directly.
    try:
        strTemp = json.dumps({"id": commandId, **dictCommand})
    except Exception:
        return {"boolSuccess": False, "data": f"Error when serializing the command {dictCommand}"}

    timeoutMs = _get_chrome_response_timeout_ms(dictCommand=dictCommand)
    deadline = monotonic() + timeoutMs / 1000

    # Some commands may complete very quickly, so register the command id before emitting.
    _dictPendingChromeCommands[commandId] = None
    emit("message_flask_to_chrome", strTemp, to=dictClients["Chrome"])

    # Wait the result to be updated by handle_result_from_chrome().
    while True:
        dictResult = _dictPendingChromeCommands.get(commandId)

        if dictResult is not None:
            # Pop the data from dictionary. it will not use again.
            _dictPendingChromeCommands.pop(commandId, None)
            return cast(DictSocketResult, dictResult)

        if monotonic() >= deadline:
            _dictPendingChromeCommands.pop(commandId, None)
            return {
                "boolSuccess": False,
                "data": (
                    "Chrome command response timed out "
                    f"after {timeoutMs} milliseconds: {dictCommand.get('commandName')}"
                ),
            }

        # Reduce performance overhead caused by idle spinning.
        sleep(0.01)


@Log.trace()
@sioServer.on("result_chrome_to_flask")
def handle_result_from_chrome(message: str) -> None:
    # Receive and update result from Chrome.

    clientSid = get_client_id()
    Log.info(f"Received result from Chrome extension: {message}, SID: {clientSid}")

    if clientSid != dictClients.get("Chrome"):
        Log.error("Ignore Chrome result from an unexpected client.")
        return

    # The result from Chrome must have been serialized correctly, so just deserialize it.
    try:
        dictResult: dict[str, Any] = json.loads(message)
    except Exception as e:
        # It should not happen.
        Log.exception_info(e)
        return

    strId = dictResult.pop("id", None)
    if strId in _dictPendingChromeCommands.keys():
        Log.debug("Update result into dictionary.")
        _dictPendingChromeCommands[strId] = dictResult
    else:
        # In case Chrome data arrives after Python has treated it as timed out.
        Log.warning(f"Ignore a late or unknown Chrome result. commandId={strId}")
