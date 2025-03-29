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

# Python use executorPackageStatus to sign its status, but the status may modified by Exectuor because "terminated" may caused by timeout or user clicked cancel button in Executor.
executorPackageStatus: Literal["error", "terminated", "running"] = "running"

processName = multiprocessing.current_process().name


@Log.trace()
def cleanup() -> None:
    # Update project.json's executorPackageStatus value for Executor update status in Task History.
    if processName != "MainProcess":
        # Only run cleanup in MainProcess.
        return None

    dictProject = json.loads(Path("project.json").read_text(encoding="utf-8"))
    strInfo = f"{PrjArgs.projectName}: "

    match executorPackageStatus:
        case "running":
            strInfo += "Completed."

        case "error":
            strInfo += "Encounter an error."

        case "terminated":
            strInfo += "You pressed Ctrl+F12 or Executor stop it."

    Log.info(strInfo)

    dictProject["executorPackageStatus"] = executorPackageStatus
    strTemp = json.dumps(dictProject, indent=4, ensure_ascii=False)
    Path("project.json").write_text(data=strTemp, encoding="utf-8", errors="strict")
    print("Update project.json: " + strTemp)

    show_notification(title="LiberRPA", message=strInfo, duration=2, wait=False)

    Log.info(f"Elapsed time: {timedelta(seconds=int(PrjArgs.elapsedTime))}")


def main() -> None:
    global boolRan
    cleanup()
    # Stop the current process
    Log.info(f"'{processName}' exit.")
    sys.exit()


if __name__ == "__main__":
    main()
