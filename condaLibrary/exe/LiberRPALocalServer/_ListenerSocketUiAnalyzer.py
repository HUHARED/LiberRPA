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

import exe.LiberRPALocalServer._UiAnalyzer as _UiAnalyzer
import exe.LiberRPALocalServer._ElementTree as _ElementTree
from exe.LiberRPALocalServer._ServerInit import sioServer, get_client_id


from flask_socketio import emit
import json
import uuid
import threading
from copy import deepcopy
from typing import Any


# Record the command be responsed or not, when the command sended to Chrome, create a new key-value pair{id:""}, when Chrome send a result with id, update it to {id:result}, and the function _wait_for_response_by_id() check it, if it's value is not "", means the result returned.
dictCommandIdResponsed: dict[str, dict[str, Any] | None] = {}

# Store the command from UI Analyzer.
dictUiAnalyzerCmd: dict[str, str] = {}

eventIsHandleUiAnalyzer = threading.Event()


@Log.trace()
@sioServer.on("uianalyzer_command")
def handle_uianalyzer_command(message: str) -> None:
    clientSid = get_client_id()
    Log.info(f"Received UI Analyzer command: {message}, SID: {clientSid}")

    strId = str(uuid.uuid4())
    dictUiAnalyzerCmd[strId] = clientSid

    result: DictSocketResult = {"boolSuccess": False, "data": None}
    temp: Any = None
    element = None
    tupleEleTree = None

    # Make sure only one uianalyzer_command can be run.
    if eventIsHandleUiAnalyzer.is_set():
        result: DictSocketResult = {
            "boolSuccess": False,
            "data": "Processing failed: An UI Analyzer command is running",
        }
        emit("message_flask_to_uianalyzer", json.dumps(result), to=dictUiAnalyzerCmd[strId])
        return None
    else:
        eventIsHandleUiAnalyzer.set()

    try:
        dictCommand = json.loads(message)
        # Delay one seconds for avoiding the mouse's up when clicking UI Analyzer's button be captured.
        # delay(1000)
        match dictCommand.get("commandName"):

            case "indicate_uia":
                while True:
                    try:
                        # If it is running in LiberRPA Local Server, some element may not useable when getattr(element, "Name"), like MenuItemControl in notepad.exe, I don't know why.
                        Log.debug("_UiAnalyzer.indicate_uia")
                        temp, element = _UiAnalyzer.indicate_uia(dictCommand["intIndicateDelaySeconds"])
                    except Exception as e:
                        Log.exception_info(e)
                        Log.debug("Retry.")
                        continue
                    else:
                        break

            case "indicate_chrome":
                temp = _UiAnalyzer.indicate_chrome(dictCommand["intIndicateDelaySeconds"], dictCommand["usePath"])
                if temp is not None:
                    tupleEleTree = temp[1]
                    temp = temp[0]

            case "indicate_image":
                temp = _UiAnalyzer.indicate_image(
                    indicateDelaySeconds=dictCommand["intIndicateDelaySeconds"],
                    grayscale=dictCommand["grayscale"],
                    confidence=dictCommand["confidence"],
                )

            case "indicate_window":
                temp = _UiAnalyzer.indicate_window(dictCommand["intIndicateDelaySeconds"])

            case "validate":
                temp = _UiAnalyzer.validate(dictCommand["strSelectorJson"], dictCommand["intMatchTimeoutSeconds"])

            case _:
                result: DictSocketResult = {
                    "boolSuccess": False,
                    "data": "Unknown command: " + str(dictCommand.get("commandName")),
                }
                Log.info(result)
                emit("message_flask_to_uianalyzer", json.dumps(result), to=dictUiAnalyzerCmd[strId])
                del dictUiAnalyzerCmd[strId]
                return None

    except Exception as e:
        result: DictSocketResult = {
            "boolSuccess": False,
            "data": "Processing failed: " + str(get_exception_info(e)),
        }
    else:
        result: DictSocketResult = {"boolSuccess": True, "data": temp}
    # preview is so long, not print it.
    if isinstance(result["data"], dict) and result["data"].get("preview") is not None:
        resultTemp = deepcopy(result)
        del resultTemp["data"]["preview"]
        Log.debug(resultTemp)
    else:
        Log.info(result)
    emit("message_flask_to_uianalyzer", json.dumps(result), to=dictUiAnalyzerCmd[strId])

    # Genarate Element Tree.
    if dictCommand.get("commandName") == "indicate_uia" and element:
        try:
            tupleTemp = _ElementTree.generate_control_tree(elementFinal=element)
        except Exception as e:
            Log.exception_info(e)
            show_notification(
                title="LiberRPA Local Server", message="Error to indicate uia\n" + str(e), duration=5, wait=False
            )
        else:
            emit("message_flask_to_uianalyzer", "Element_Tree:" + json.dumps(tupleTemp), to=dictUiAnalyzerCmd[strId])

    if dictCommand.get("commandName") == "indicate_chrome" and tupleEleTree:
        emit("message_flask_to_uianalyzer", "Element_Tree:" + json.dumps(tupleEleTree), to=dictUiAnalyzerCmd[strId])

    del dictUiAnalyzerCmd[strId]
    eventIsHandleUiAnalyzer.clear()
