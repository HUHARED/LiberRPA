# FileName: _ListenerSocketChrome.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketChrome ===")
from liberrpa.Logging import Log
from liberrpa.Common._ProtocolValidation import ensure_socket_result
from liberrpa.Common._TypedValue import DictSocketResult
from liberrpa.LiberRPALocalServer._ServerInit import sioServer, dictClients, get_client_id


from flask_socketio import emit
import json
import uuid
from dataclasses import dataclass
from time import monotonic
from threading import Event, Lock
from typing import Any

# Chrome commands use milliseconds for business timeouts.
# This listener timeout is only a communication fallback.
# It should be slightly longer than the Chrome-side timeout, so Chrome can return its own timeout result first.
_DEFAULT_CHROME_COMMAND_TIMEOUT_MS = 15000
_CHROME_RESPONSE_GRACE_MS = 3000
_CLOSE_CURRENT_TAB_POLL_INTERVAL_SECONDS = 0.1

_SERVER_WAIT_ID_KEY = "ServerWaitId"


@dataclass(slots=True)
class _PendingChromeCommand:
    event: Event
    result: DictSocketResult | None = None


# Pending Chrome commands are shared by Socket.IO handler threads.
# Use a lock to avoid races between sending commands, receiving responses, and cleaning up timed-out commands.
_pendingChromeCommandLock = Lock()
_dictPendingChromeCommands: dict[str, _PendingChromeCommand] = {}


@Log.trace()
@sioServer.on("chrome_extension_connect")
def handle_chrome_extension_connect(message: dict[str, str]) -> None:
    # Save the Chrome extension's sid for sending commands to it later. Called by Chrome extension.
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

    # If the Chrome extension is working, send command to it and wait for the result.
    result: DictSocketResult = _wait_for_response_by_id(
        commandId=strId, dictCommand=dictCommand
    )

    return result


def _get_chrome_response_timeout_ms(dictCommand: dict[str, Any]) -> int:
    timeout = dictCommand.get("timeout")

    if type(timeout) is int and timeout > 0:
        return timeout + _CHROME_RESPONSE_GRACE_MS

    return _DEFAULT_CHROME_COMMAND_TIMEOUT_MS + _CHROME_RESPONSE_GRACE_MS


def _wait_for_response_by_id(
    commandId: str, dictCommand: dict[str, Any]
) -> DictSocketResult:

    # If dictCommand can't be serialized, return an error result directly.
    try:
        if _SERVER_WAIT_ID_KEY in dictCommand.keys():
            raise KeyError(
                "Unexpected internal state: 'ServerWaitId' is a built-in key in Local Server."
            )

        strTemp = json.dumps({_SERVER_WAIT_ID_KEY: commandId, **dictCommand})
    except Exception as e:
        Log.exception_info(e)
        return {
            "boolSuccess": False,
            "data": f"Error when serializing the Chrome command: {dictCommand}",
        }

    chromeSid = dictClients.get("Chrome")
    if chromeSid is None:
        return {
            "boolSuccess": False,
            "data": "Can't access Chrome extension, you should install it and turn it on, and make sure Chrome is running.",
        }

    timeoutWithGraceMs = _get_chrome_response_timeout_ms(dictCommand=dictCommand)

    pendingCommand = _PendingChromeCommand(event=Event())

    # Register before emit(), because Chrome may return very quickly.
    with _pendingChromeCommandLock:
        _dictPendingChromeCommands[commandId] = pendingCommand

    try:
        emit("message_flask_to_chrome", strTemp, to=chromeSid)

        # Closing the last Chrome tab can also close the browser before the extension has time to return its normal command acknowledgement.
        if dictCommand.get("commandName") == "closeCurrentTab":
            floatDeadline = monotonic() + timeoutWithGraceMs / 1000

            while True:
                floatRemaining = floatDeadline - monotonic()
                if floatRemaining <= 0:
                    return {
                        "boolSuccess": False,
                        "data": (
                            f"Chrome command response timed out after {timeoutWithGraceMs} milliseconds: {dictCommand.get('commandName')}"
                        ),
                    }

                if pendingCommand.event.wait(
                    timeout=min(_CLOSE_CURRENT_TAB_POLL_INTERVAL_SECONDS, floatRemaining)
                ):
                    break

                if dictClients.get("Chrome") is None:
                    Log.debug(
                        "The Chrome extension disconnected while closing the current tab. "
                        "Treat the command as successful."
                    )
                    return {"boolSuccess": True, "data": None}

        else:
            # Wait until handle_result_from_chrome() sets the event, or until the communication fallback timeout expires.
            if not pendingCommand.event.wait(timeout=timeoutWithGraceMs / 1000):
                return {
                    "boolSuccess": False,
                    "data": (
                        "Chrome command response timed out "
                        f"after {timeoutWithGraceMs} milliseconds: {dictCommand.get('commandName')}"
                    ),
                }

        if pendingCommand.result is None:
            return {
                "boolSuccess": False,
                "data": "Chrome command returned no result.",
            }

        return pendingCommand.result
    except Exception as e:
        Log.exception_info(e)
        return {
            "boolSuccess": False,
            "data": f"Error when sending Chrome command: {dictCommand.get('commandName')}",
        }
    finally:
        # Remove both completed and timed-out commands.
        with _pendingChromeCommandLock:
            _dictPendingChromeCommands.pop(commandId, None)


@Log.trace()
@sioServer.on("result_chrome_to_flask")
def handle_result_from_chrome(message: str) -> None:
    # Receive and update result from Chrome.

    clientSid = get_client_id()

    if not isinstance(message, str):
        Log.warning(
            "Ignore an invalid Chrome result payload. "
            f"Expected str, got {type(message).__name__}."
        )
        return None

    intPayloadLength = len(message)
    Log.debug(
        f"Received Chrome result payload. SID={clientSid}, serializedLength={intPayloadLength}"
    )

    if clientSid != dictClients.get("Chrome"):
        Log.error("Ignore Chrome result from an unexpected client.")
        return

    # The result from Chrome must have been serialized correctly, so just deserialize it.
    try:
        rawResult = json.loads(message)
    except Exception as e:
        Log.exception_info(e)
        return

    if not isinstance(rawResult, dict):
        Log.warning(
            f"Ignore an invalid Chrome result. Expected dict, got {type(rawResult).__name__}."
        )
        return

    strId = rawResult.pop(_SERVER_WAIT_ID_KEY, None)
    if not isinstance(strId, str):
        Log.warning("Ignore a Chrome result without a valid command id.")
        return

    try:
        dictResult = ensure_socket_result(rawResult, source="Chrome extension")
    except ValueError as e:
        Log.warning(str(e))
        return None

    Log.debug(
        "Validated Chrome result. "
        f"commandId={strId}, boolSuccess={dictResult['boolSuccess']}, "
        f"dataType={type(dictResult['data']).__name__}, serializedLength={intPayloadLength}"
    )

    with _pendingChromeCommandLock:
        pendingCommand = _dictPendingChromeCommands.get(strId)

        if pendingCommand is None:
            # In case Chrome data arrives after Python has treated it as timed out.
            Log.warning(f"Ignore a late or unknown Chrome result. commandId={strId}")
            return

        Log.debug("Update Chrome command result.")
        pendingCommand.result = dictResult
        pendingCommand.event.set()
