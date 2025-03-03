# FileName: _ListenerSocketRecord.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketRecord ===")
from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictSocketResult
from liberrpa.Common._Exception import get_exception_info

import exe.LiberRPALocalServer._Record as _Record
from exe.LiberRPALocalServer._ServerInit import sioServer, get_client_id


import threading
from typing import Any


@Log.trace()
@sioServer.on("record_command")
def handle_record_command(dictCommand: dict[str, Any]) -> DictSocketResult:
    Log.info(f"Received Record command: {dictCommand}, SID: {get_client_id()}")

    result: DictSocketResult = {"boolSuccess": True, "data": None}

    try:
        match dictCommand.get("commandName"):
            case "video":
                # Use threading to avoid blocking the Python.
                threadingRecording = threading.Thread(
                    target=_start_recording, args=(dictCommand["pid"], dictCommand["folderName"])
                )
                threadingRecording.start()
                return {"boolSuccess": True, "data": "$SIGN-START_RECORD_VIDEO"}

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
        Log.info(result)
        return result


def _start_recording(pid: int, folderName: str) -> None:
    # Call the record_screen function
    _Record.record_screen(pid=pid, folderName=folderName)
