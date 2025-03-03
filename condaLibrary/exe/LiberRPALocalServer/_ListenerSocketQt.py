# FileName: _ListenerSocketQt.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketQt ===")
from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictSocketResult
from liberrpa.Common._Exception import get_exception_info

import exe.LiberRPALocalServer._Qt as _Qt
from exe.LiberRPALocalServer._ServerInit import sioServer, get_client_id


from typing import Any


@Log.trace()
@sioServer.on("qt_command")
def handle_qt_command(dictCommand: dict[str, Any]) -> DictSocketResult:
    Log.info(f"Received Record command: {dictCommand}, SID: {get_client_id()}")

    result: DictSocketResult = {"boolSuccess": True, "data": None}
    temp: Any = None

    try:
        match dictCommand.get("commandName"):
            case "show_notification":
                temp = _Qt.show_notification(
                    title=dictCommand["title"],
                    message=dictCommand["message"],
                    duration=dictCommand["duration"],
                    wait=dictCommand["wait"],
                )

            case "create_overlay":
                temp = _Qt.create_overlay(
                    x=dictCommand["x"],
                    y=dictCommand["y"],
                    width=dictCommand["width"],
                    height=dictCommand["height"],
                    color=dictCommand["color"],
                    duration=dictCommand["duration"],
                    label=dictCommand["label"],
                )

            case "create_area":
                temp = _Qt.create_area(
                    x=dictCommand["x"],
                    y=dictCommand["y"],
                    width=dictCommand["width"],
                    height=dictCommand["height"],
                    fontFamily=dictCommand["fontFamily"],
                    fontSize=dictCommand["fontSize"],
                    fontColor=dictCommand["fontColor"],
                )
                listAreaCache = _Qt.dictClientAreaCache.get(get_client_id(), None)
                if not listAreaCache:
                    _Qt.dictClientAreaCache[get_client_id()] = [temp]
                else:
                    _Qt.dictClientAreaCache[get_client_id()].append(temp)
                Log.info(f"dictClientAreaCache={_Qt.dictClientAreaCache}")

            case "display_text":
                temp = _Qt.display_text(
                    screenPrintObj=dictCommand["screenPrintObj"],
                    text=dictCommand["text"],
                )

            case "clean_text":
                temp = _Qt.clean_text(screenPrintObj=dictCommand["screenPrintObj"])

            case "close_area":
                temp = _Qt.close_area(screenPrintObj=dictCommand["screenPrintObj"])
                _Qt.dictClientAreaCache[get_client_id()].remove(dictCommand["screenPrintObj"])
                Log.info(f"dictClientAreaCache={_Qt.dictClientAreaCache}")

            case _:
                result: DictSocketResult = {
                    "boolSuccess": False,
                    "data": "Unknown command: " + str(dictCommand.get("commandName")),
                }
                return result

    except Exception as e:
        result: DictSocketResult = {
            "boolSuccess": False,
            "data": "Processing failed: " + str(get_exception_info(e)),
        }
    else:
        result: DictSocketResult = {"boolSuccess": True, "data": temp}
    Log.info(result)
    return result
