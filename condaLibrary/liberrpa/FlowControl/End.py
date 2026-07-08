# FileName: End.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._Utils import PATH_PROJECT_JSON, PROCESS_NAME
import liberrpa.UI._TerminableThread as _TerminableThread
from liberrpa.Dialog import show_notification
from liberrpa.FlowControl.ProjectFlowInit import PrjArgs

from datetime import timedelta
import sys
import json
from typing import Literal

# Python use executorPackageStatus to sign its status, but the status may modified by Executor because "terminated" may caused by timeout or user clicked cancel button in Executor.
executorPackageStatus: Literal["error", "terminated", "running"] = "running"


@Log.trace()
def cleanup() -> None:
    # Update project.json's executorPackageStatus value for Executor update status in Task History.
    if PROCESS_NAME != "MainProcess":
        # Only run cleanup in MainProcess.
        return None

    dictProject = json.loads(PATH_PROJECT_JSON.read_text(encoding="utf-8"))
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
    PATH_PROJECT_JSON.write_text(data=strTemp, encoding="utf-8", errors="strict")
    print("Update project.json: " + strTemp)

    show_notification(title="LiberRPA", message=strInfo, duration=2, wait=False)

    Log.info(f"Elapsed time: {timedelta(seconds=int(PrjArgs.elapsedTime))}")

    """
    Summarize unsafe timeout fallback events at process end.
    These counters are read from the module instead of imported by value, because integers are immutable and `from module import counter` would not track later rebinding in _TerminableThread.
    """
    if _TerminableThread.intUnsafeThreadTerminationCount > 0 or _TerminableThread.intUnstoppableThreadCount > 0:
        strTemp = ""

        if _TerminableThread.intUnsafeThreadTerminationCount > 0:
            # The worker thread was actually interrupted by injected exception and then stopped.
            strTemp += (
                f"Unsafe timeout fallback interrupted worker threads "
                f"{_TerminableThread.intUnsafeThreadTerminationCount} times. "
            )

        if _TerminableThread.intUnstoppableThreadCount > 0:
            # The worker thread could not be stopped. The specific call raised UiUnstoppableThreadError.
            strTemp += (
                f"Unsafe timeout fallback failed to stop worker threads "
                f"{_TerminableThread.intUnstoppableThreadCount} times. "
            )

        Log.critical(
            strTemp + "This means a UI or third-party call did not return in time. "
            "Please report this case with logs if it happens repeatedly."
        )


def main() -> None:
    cleanup()
    # Stop the current process
    Log.info(f"'{PROCESS_NAME}' exit.")
    sys.exit()


if __name__ == "__main__":
    main()
