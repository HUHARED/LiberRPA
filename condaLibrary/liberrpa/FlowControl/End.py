# FileName: End.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Dialog import show_notification
from liberrpa.FlowControl.ProjectFlowInit import PrjArgs

from datetime import timedelta
import sys
import multiprocessing
import json
from pathlib import Path
from typing import Literal

exitReason: Literal["error", "manual", ""] = ""

processName = multiprocessing.current_process().name


@Log.trace()
def cleanup() -> None:
    # If the main process has an uncaught error or was stopped manually, record it.
    if processName == "MainProcess":
        if exitReason != "":
            dictProject = json.loads(Path("project.json").read_text(encoding="utf-8"))
            dictProject["exitReason"] = exitReason
            strTemp = json.dumps(dictProject, indent=4, ensure_ascii=False)
            Path("project.json").write_text(data=strTemp, encoding="utf-8", errors="strict")
            print("Update project.json: " + strTemp)
            if exitReason == "manual":
                strInfo = f"You pressed Ctrl+F12, forcing the program '{PrjArgs.projectName}' to exit."
                Log.critical(strInfo)
                show_notification(title="LiberRPA", message=strInfo, duration=2)
            else:
                # "error"
                show_notification(title="LiberRPA", message=f"'{PrjArgs.projectName}' encounters an error.", duration=2)
    else:
        # Run completed.
        show_notification(title="LiberRPA", message=f"'{PrjArgs.projectName}' completed.", duration=2)

    Log.info(f"Elapsed time: {timedelta(seconds=int(PrjArgs.elapsedTime))}")


def main() -> None:
    global boolRan
    cleanup()
    # Stop the current process
    Log.info(f"'{processName}' exit.")
    sys.exit()


if __name__ == "__main__":
    main()
