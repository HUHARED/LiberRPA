# FileName: _ListenerSocketApplication.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketApplication ===")
from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictSocketResult
from liberrpa.Common._Exception import get_exception_info

from exe.LiberRPALocalServer._ServerInit import sioServer, dictClients, get_client_id
import exe.LiberRPALocalServer._Application as _Application

from typing import Any


@Log.trace()
@sioServer.on("application_command")
def handle_application_command(dictCommand: dict[str, Any]) -> DictSocketResult:
    Log.info(f"Received Application command: {dictCommand}, SID: {get_client_id()}")

    result: DictSocketResult = {"boolSuccess": True, "data": None}
    temp: Any = None

    try:
        match dictCommand.get("commandName"):

            case "run_application":
                temp = _Application.run_application(
                    filePath=dictCommand["filePath"], windowState=dictCommand["windowState"]
                )

            case "open_url":
                temp = _Application.open_url(url=dictCommand["url"])

            case "open_browser":
                temp = _Application.open_browser(
                    url=dictCommand["url"], path=dictCommand["path"], params=dictCommand["params"]
                )

            case "get_chrome_socket_id":
                # print(dictClients)
                temp = dictClients.get("Chrome")

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
