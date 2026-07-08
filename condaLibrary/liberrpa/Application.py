# FileName: Application.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command
from liberrpa.Common._TypedValue import StrPath

import psutil
import os
from typing import Literal


@Log.trace()
def run_application(filePath: StrPath, windowState: Literal["default", "maximize", "minimize"] = "default") -> int:
    """
    Run an application with a specified window state.

    Parameters:
        filePath: The path of the application to run. Accepts str or PathLike[str].
        windowState: 'default', 'maximize', 'minimize'

    Returns:
        int: The application's PID.
    """

    # NOTE: Use LiberRPA Local Server to run the application. If use subprocess or os module to run the application in the current Python process, it will kill the new application when the Python process exits(when the application process is the first process instance).

    dictCommand = {
        "commandName": "run_application",
        "filePath": os.fspath(filePath),
        "windowState": windowState,
    }

    pid: int = send_command(eventName="application_command", command=dictCommand)

    return pid


@Log.trace()
def open_url(url: str) -> None:
    """
    Open a file or webpage using the default application.

    Parameters:
        url: The URL of the target file or webpage. It may need to start with a protocol (e.g., http:// or https://)
    """
    # NOTE: Use LiberRPA Local Server to run the application. Due to it has the same problem like run_application.

    dictCommand = {"commandName": "open_url", "url": url}

    send_command(eventName="application_command", command=dictCommand)


@Log.trace()
def check_process_running(nameOrPid: str | int) -> bool:
    """
    Check whether an application is running by its name or PID.

    Parameters:
        nameOrPid: the process name or PID.

    Returns:
        bool: If the process is running, return True, otherwise return False.
    """
    for process in psutil.process_iter(["pid", "name"]):
        try:
            if process.pid == nameOrPid or process.name().lower() == str(nameOrPid).lower():
                if process.status() == psutil.STATUS_RUNNING:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # psutil may raise an AccessDenied or NoSuchProcess error. These should be handled.
            continue

    return False


@Log.trace()
def stop_process(nameOrPid: str | int) -> None:
    """
    Stop(kill) an application by its name or PID.

    Parameters:
        nameOrPid: the process name or PID.
    """
    for process in psutil.process_iter(["pid", "name"]):
        if process.pid == nameOrPid or (isinstance(nameOrPid, str) and process.name().lower() == nameOrPid.lower()):
            process.kill()


if __name__ == "__main__":
    # print(check_process_running(nameOrPid="notepad.exe"))
    open_url(url=R"http://www.google.com")
    # pid = run_application(filePath=R"C:\Windows\System32\notepad.exe", windowState="minimize")
    # print("pid" + str(pid))
    # stop_process(nameOrPid=6608)
    # print(check_process_running(nameOrPid="notepad.exe"))
    # stop_process(nameOrPid=pid)
    print("Done.")
