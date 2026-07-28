# FileName: _ListenerSocketUiAnalyzer.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketUiAnalyzer ===")
from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictSocketResult
from liberrpa.Common._Exception import get_exception_info
from liberrpa.Dialog import show_notification

import liberrpa.LiberRPALocalServer._UiAnalyzer as _UiAnalyzer
import liberrpa.LiberRPALocalServer._ElementTree as _ElementTree
from liberrpa.LiberRPALocalServer._ServerInit import sioServer, get_client_id
from liberrpa.LiberRPALocalServer._Tray import change_tray_icon


from flask_socketio import emit
import json
import threading
from copy import deepcopy
from typing import Any

# Make sure only one UI Analyzer command is handled at a time.
_lockHandleUiAnalyzer = threading.Lock()


@Log.trace()
@sioServer.on("uianalyzer_command")
def handle_uianalyzer_command(message: str) -> None:
    clientSid = get_client_id()
    Log.info(f"Received UI Analyzer command: {message}, SID: {clientSid}")

    if not _lockHandleUiAnalyzer.acquire(blocking=False):
        result: DictSocketResult = {
            "boolSuccess": False,
            "data": "Error: Another UI Analyzer command is running",
        }
        Log.debug("Another UI Analyzer command is running.")
        emit(
            "message_flask_to_uianalyzer",
            json.dumps(result),
            to=clientSid,
        )
        return None

    result: DictSocketResult = {"boolSuccess": False, "data": None}
    dictCommand: dict[str, Any] = {}
    strCommandName: str | None = None
    temp: Any = None
    element = None
    tupleEleTree = None

    try:
        change_tray_icon(component="LiberRPALocalServer_Indicating")

        dictCommand = json.loads(message)
        strCommandNameTemp = dictCommand.get("commandName")
        if not isinstance(strCommandNameTemp, str):
            raise ValueError(f"Invalid commandName: {strCommandNameTemp!r}")

        strCommandName = strCommandNameTemp

        # Check some arguments to avoid incompatible argument and too long delays in case. (e.g. Local Server's version doesn't equal to UI Analyzer's version)
        if strCommandName in ["indicate_uia", "indicate_chrome", "indicate_image", "indicate_window"]:
            intIndicateDelay = dictCommand["intIndicateDelaySeconds"]
            if type(intIndicateDelay) is not int or intIndicateDelay < 1 or intIndicateDelay > 10:
                raise ValueError(
                    f"Invalid UI Analyzer indicate delay: {intIndicateDelay!r}. Expected an integer from 1 to 10."
                )

        if strCommandName == "validate":
            intMatchTimeout = dictCommand["intMatchTimeoutSeconds"]
            if type(intMatchTimeout) is not int or intMatchTimeout < 3 or intMatchTimeout > 60:
                raise ValueError(
                    f"Invalid UI Analyzer match timeout: {intMatchTimeout!r}. Expected an integer from 3 to 60."
                )

        match strCommandName:
            case "indicate_uia":
                # NOTE: If it is running in LiberRPA Local Server, some element may not useable when getattr(element, "Name"), like MenuItemControl in notepad.exe, I don't know why yet.
                Log.debug("_UiAnalyzer.indicate_uia")
                temp, element = _UiAnalyzer.indicate_uia(intIndicateDelay)

            case "indicate_chrome":
                temp = _UiAnalyzer.indicate_chrome(intIndicateDelay, dictCommand["usePath"])
                if temp is not None:
                    tupleEleTree = temp[1]
                    temp = temp[0]

            case "indicate_image":
                temp = _UiAnalyzer.indicate_image(
                    indicateDelaySeconds=intIndicateDelay,
                    grayscale=dictCommand["grayscale"],
                    confidence=dictCommand["confidence"],
                )

            case "indicate_window":
                temp = _UiAnalyzer.indicate_window(intIndicateDelay)

            case "validate":
                temp = _UiAnalyzer.validate(dictCommand["strSelectorJson"], intMatchTimeout)

            case _:
                raise ValueError(f"Unknown command: {strCommandName}")

    except Exception as e:
        result: DictSocketResult = {
            "boolSuccess": False,
            "data": "Error: " + str(get_exception_info(e)),
        }
    else:
        result: DictSocketResult = {"boolSuccess": True, "data": temp}

    try:
        # preview is so long, not print it.
        if isinstance(result["data"], dict) and result["data"].get("preview") is not None:
            resultTemp = deepcopy(result)

            resultDataTemp = resultTemp.get("data")
            if isinstance(resultDataTemp, dict):
                resultDataTemp.pop("preview", None)

            Log.debug(resultTemp)
        else:
            Log.info(result)

        emit(
            "message_flask_to_uianalyzer",
            json.dumps(result),
            to=clientSid,
        )

        # Generate Element Tree.
        if strCommandName == "indicate_uia" and element:
            try:
                tupleTemp = _ElementTree.generate_control_tree(elementFinal=element)
            except Exception as e:
                Log.exception_info(e)
                show_notification(
                    title="LiberRPA Local Server",
                    message="Error to indicate uia\n" + str(e),
                    duration=5,
                    wait=False,
                )
            else:
                emit(
                    "message_flask_to_uianalyzer",
                    "Element_Tree:" + json.dumps(tupleTemp),
                    to=clientSid,
                )

        if strCommandName == "indicate_chrome" and tupleEleTree:
            emit(
                "message_flask_to_uianalyzer",
                "Element_Tree:" + json.dumps(tupleEleTree),
                to=clientSid,
            )
    except Exception as e:
        Log.error(get_exception_info(e))
    finally:
        _lockHandleUiAnalyzer.release()
        change_tray_icon(component="LiberRPALocalServer")
