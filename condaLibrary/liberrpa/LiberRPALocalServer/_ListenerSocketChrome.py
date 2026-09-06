# FileName: _ListenerSocketChrome.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketChrome ===")
from liberrpa.Logging import Log
from liberrpa.Common._ProtocolValidation import ensure_socket_result
from liberrpa.Common._TypedValue import DictSocketResult
from liberrpa.LiberRPALocalServer._ServerInit import (
    dictClients,
    ensure_client_type,
    get_client_id,
    sioServer,
)


from flask_socketio import emit
import json
import uuid
from dataclasses import dataclass
from threading import Event, Lock
from typing import Any

# Chrome commands use milliseconds for business timeouts.
# This listener timeout is only a communication fallback.
# It should be slightly longer than the Chrome-side timeout, so Chrome can return its own timeout result first.
_DEFAULT_CHROME_COMMAND_TIMEOUT_MS = 15000
_CHROME_RESPONSE_GRACE_MS = 3000

_SERVER_WAIT_ID_KEY = "ServerWaitId"


@dataclass(slots=True)
class _PendingChromeCommand:
    event: Event
    chromeSid: str
    commandName: str
    result: DictSocketResult | None = None


# Pending Chrome commands are shared by Socket.IO handler threads.
# Use a lock to coordinate command registration, responses, disconnect cleanup, and connection replacement.
_pendingChromeCommandLock = Lock()
_dictPendingChromeCommands: dict[str, _PendingChromeCommand] = {}


def _get_chrome_disconnect_result(
    pendingCommand: _PendingChromeCommand,
) -> DictSocketResult:
    # Some Chrome environments, especially portable installations, may terminate the extension connection immediately after closing the last tab, before the normal closeCurrentTab acknowledgement is returned.
    # Treat that target connection disconnect as successful only for closeCurrentTab.
    if pendingCommand.commandName == "closeCurrentTab":
        return {"boolSuccess": True, "data": None}

    return {
        "boolSuccess": False,
        "data": (
            "Chrome extension disconnected before completing command: "
            f"{pendingCommand.commandName}."
        ),
    }


def disconnect_chrome_client(clientSid: str) -> bool:
    """Remove a disconnected Chrome client and settle commands sent to that connection."""
    listPendingCommand: list[tuple[str, _PendingChromeCommand]] = []

    with _pendingChromeCommandLock:
        boolWasActiveClient = dictClients.get("Chrome") == clientSid
        if boolWasActiveClient:
            dictClients.pop("Chrome", None)

        for commandId, pendingCommand in list(_dictPendingChromeCommands.items()):
            if pendingCommand.chromeSid != clientSid or pendingCommand.event.is_set():
                continue

            _dictPendingChromeCommands.pop(commandId, None)
            pendingCommand.result = _get_chrome_disconnect_result(pendingCommand)
            # Publish the terminal result and wake its waiter before diagnostic logging.
            pendingCommand.event.set()
            listPendingCommand.append((commandId, pendingCommand))

    for commandId, pendingCommand in listPendingCommand:
        if pendingCommand.commandName == "closeCurrentTab":
            Log.debug(
                "The target Chrome connection disconnected while closing the current tab. "
                "Treat the command as successful. "
                f"commandId={commandId}, SID={clientSid}"
            )
        else:
            Log.warning(
                "Fail a pending Chrome command because its target connection disconnected. "
                f"commandId={commandId}, commandName={pendingCommand.commandName}, SID={clientSid}"
            )

    return boolWasActiveClient


@Log.trace()
@sioServer.on("chrome_extension_connect")
def handle_chrome_extension_connect(message: object) -> None:
    # Save the Chrome extension's sid for sending commands to it later. Called by Chrome extension.
    clientSid = get_client_id()

    try:
        ensure_client_type(expectedClientType="chrome", clientSid=clientSid)
    except PermissionError as e:
        Log.warning(str(e))
        return None

    if not isinstance(message, str):
        Log.warning(
            "Ignore an invalid Chrome connection message. "
            f"Expected str, got {type(message).__name__}."
        )
        return None

    Log.info(f"Chrome connection established. {message}, SID: {clientSid}")

    with _pendingChromeCommandLock:
        previousChromeSid = dictClients.get("Chrome")
        dictClients["Chrome"] = clientSid

    if previousChromeSid is not None and previousChromeSid != clientSid:
        Log.info(
            "Use the new Chrome connection for subsequent commands. "
            "Commands already sent remain bound to their original connection. "
            f"previousSID={previousChromeSid}, currentSID={clientSid}"
        )

    Log.info(f"The Chrome clients: {dictClients}")


@Log.trace()
@sioServer.on("chrome_command")
def handle_chrome_command(dictCommand: dict[str, Any]) -> DictSocketResult:
    # The entrance for all Chrome functions to execution, call by Chrome.py.
    clientSid = get_client_id()

    try:
        ensure_client_type(expectedClientType="python", clientSid=clientSid)
    except PermissionError as e:
        return {"boolSuccess": False, "data": "Error: " + str(e)}

    Log.info(f"Received Chrome command: {dictCommand}, SID: {clientSid}")

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

    commandNameValue = dictCommand.get("commandName")
    commandName = commandNameValue if isinstance(commandNameValue, str) else "<unknown>"
    timeoutWithGraceMs = _get_chrome_response_timeout_ms(dictCommand=dictCommand)

    # Read the active Chrome SID and register the command under the same lock used by disconnect cleanup.
    # This prevents a command from being registered for a connection that was removed between those steps.
    with _pendingChromeCommandLock:
        chromeSid = dictClients.get("Chrome")
        if chromeSid is None:
            return {
                "boolSuccess": False,
                "data": "Can't access Chrome extension, you should install it and turn it on, and make sure Chrome is running.",
            }

        pendingCommand = _PendingChromeCommand(
            event=Event(),
            chromeSid=chromeSid,
            commandName=commandName,
        )

        # Register before emit(), because Chrome may return very quickly.
        _dictPendingChromeCommands[commandId] = pendingCommand

    try:
        emit("message_flask_to_chrome", strTemp, to=chromeSid)

        # Responses and disconnect handling both publish a result and signal the same event.
        if not pendingCommand.event.wait(timeout=timeoutWithGraceMs / 1000):
            return {
                "boolSuccess": False,
                "data": (
                    "Chrome command response timed out "
                    f"after {timeoutWithGraceMs} milliseconds: {pendingCommand.commandName}"
                ),
            }

        if pendingCommand.result is None:
            return {
                "boolSuccess": False,
                "data": "Chrome command returned no result.",
            }

        return pendingCommand.result
    except Exception as e:
        # Connection teardown or a fast response may already have settled this command.
        if pendingCommand.event.is_set() and pendingCommand.result is not None:
            return pendingCommand.result

        Log.exception_info(e)
        return {
            "boolSuccess": False,
            "data": f"Error when sending Chrome command: {pendingCommand.commandName}",
        }
    finally:
        # Disconnect cleanup may already have removed this command.
        with _pendingChromeCommandLock:
            _dictPendingChromeCommands.pop(commandId, None)


@Log.trace()
@sioServer.on("result_chrome_to_flask")
def handle_result_from_chrome(message: object) -> None:
    # Receive and update result from Chrome.

    clientSid = get_client_id()

    try:
        ensure_client_type(expectedClientType="chrome", clientSid=clientSid)
    except PermissionError as e:
        Log.warning(str(e))
        return None

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
            # In case Chrome data arrives after Python has treated it as timed out or disconnected.
            Log.warning(f"Ignore a late or unknown Chrome result. commandId={strId}")
            return

        if clientSid != pendingCommand.chromeSid:
            Log.error(
                "Ignore Chrome result from a connection that did not receive the command. "
                f"commandId={strId}, expectedSID={pendingCommand.chromeSid}, actualSID={clientSid}"
            )
            return None

        if pendingCommand.event.is_set():
            Log.warning(f"Ignore a duplicate Chrome result. commandId={strId}")
            return None

        Log.debug("Update Chrome command result.")
        pendingCommand.result = dictResult
        pendingCommand.event.set()
