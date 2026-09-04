# FileName: _Application.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import StrPath

import subprocess
import win32api
import win32con
import win32event
import win32gui
import win32process
import pywintypes
import psutil
import webbrowser
import urllib.parse
import os
from pathlib import Path
from time import monotonic, sleep
from typing import Literal


_INT_APPLICATION_READY_TIMEOUT = 10000
_INT_INPUT_IDLE_FAST_TIMEOUT = 1000
_FLOAT_APPLICATION_READY_POLL_INTERVAL = 0.1


def _wait_for_process_input_idle(intProcessId: int, intTimeout: int) -> bool | None:
    """
    Try a short WaitForInputIdle check.

    Returns:
        True: The process reached input-idle, or Windows reports it as immediately ready.
        False: The wait timed out.
        None: The readiness check could not be performed reliably.
    """

    processHandle = None

    try:
        processHandle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE,
            False,
            intProcessId,
        )
        intWaitResult = win32event.WaitForInputIdle(processHandle, intTimeout)

        if intWaitResult == win32event.WAIT_OBJECT_0:
            return True

        if intWaitResult == win32event.WAIT_TIMEOUT:
            return False

        return None

    except pywintypes.error:
        # WaitForInputIdle is only a fast path. Some processes do not expose a suitable GUI message queue, so fall back to process-tree/window checks.
        return None

    finally:
        if processHandle is not None:
            win32api.CloseHandle(processHandle)


def _collect_process_tree_ids(setProcessIds: set[int]) -> None:
    """Add currently observable descendants of the launched process tree."""

    # Keep previously observed PIDs. A launcher may exit after creating the actual application process, so rebuilding only from the original PID can lose a child after its parent disappears.
    for intProcessId in tuple(setProcessIds):
        try:
            processObj = psutil.Process(intProcessId)
            listChildren = processObj.children(recursive=False)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        for childProcess in listChildren:
            setProcessIds.add(childProcess.pid)


def _find_visible_window_process_id(setProcessIds: set[int]) -> int | None:
    """Return the PID of a visible top-level window in the launched process tree."""

    intResult: int | None = None

    def enum_window_callback(intHandle: int, _: object) -> bool:
        nonlocal intResult

        # Do not stop EnumWindows by returning False after a match.
        # A callback that returns False also makes EnumWindows return zero, which PyWin32 can surface as a pywintypes.error instead of a normal early exit.
        if intResult is not None:
            return True

        try:
            if not win32gui.IsWindowVisible(intHandle):
                return True

            _, intProcessId = win32process.GetWindowThreadProcessId(intHandle)
        except Exception:
            # A window may disappear while EnumWindows results are being processed.
            return True

        if intProcessId in setProcessIds:
            intResult = intProcessId

        return True

    win32gui.EnumWindows(enum_window_callback, None)
    return intResult


def _wait_for_application_ready(processObj: subprocess.Popen[bytes]) -> int:
    """
    Wait for the launched application to expose a usable GUI process when possible.

    Ordinary applications can return through the short input-idle fast path.
    Launcher and one-file applications may instead create a descendant process that owns the actual visible top-level window; in that case, return that PID.

    If readiness cannot be determined within the timeout, log a warning and return the original PID.
    """

    intOriginalProcessId = processObj.pid
    floatDeadline = monotonic() + _INT_APPLICATION_READY_TIMEOUT / 1000
    setProcessIds = {intOriginalProcessId}

    # Fast path for ordinary GUI applications and processes for which Windows reports input-idle waiting as immediately complete.
    # This also avoids making non-GUI applications pay the full GUI readiness timeout.
    intFastTimeout = min(
        _INT_INPUT_IDLE_FAST_TIMEOUT,
        max(0, int((floatDeadline - monotonic()) * 1000)),
    )
    boolInputIdle = _wait_for_process_input_idle(
        intProcessId=intOriginalProcessId,
        intTimeout=intFastTimeout,
    )

    _collect_process_tree_ids(setProcessIds=setProcessIds)
    intWindowProcessId = _find_visible_window_process_id(setProcessIds=setProcessIds)
    if intWindowProcessId is not None:
        return intWindowProcessId

    if boolInputIdle is True:
        return intOriginalProcessId

    while monotonic() < floatDeadline:
        _collect_process_tree_ids(setProcessIds=setProcessIds)

        intWindowProcessId = _find_visible_window_process_id(setProcessIds=setProcessIds)
        if intWindowProcessId is not None:
            return intWindowProcessId

        sleep(_FLOAT_APPLICATION_READY_POLL_INTERVAL)

    Log.warning(
        f"The launched application was not detected as ready within {_INT_APPLICATION_READY_TIMEOUT} ms. Continue anyway. PID={intOriginalProcessId}"
    )
    return intOriginalProcessId


def run_application(
    filePath: StrPath,
    workingDirectory: StrPath,
    windowState: Literal["default", "maximize", "minimize"] = "default",
) -> int:
    match windowState:
        case "maximize":
            showState = win32con.SW_SHOWMAXIMIZED
        case "minimize":
            showState = win32con.SW_SHOWMINIMIZED
        case _:
            # default or error input
            showState = win32con.SW_SHOWNORMAL

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = showState

    processObj = subprocess.Popen(
        [filePath],
        cwd=workingDirectory,
        startupinfo=startupinfo,
        creationflags=subprocess.DETACHED_PROCESS,
    )

    return _wait_for_application_ready(processObj=processObj)


def open_url(url: str) -> None:
    parsedUrl = urllib.parse.urlparse(url)

    if parsedUrl.scheme in ["http", "https"]:
        webbrowser.open(url)
    elif os.path.exists(Path(url).resolve()):
        webbrowser.open(url)
    else:
        raise FileNotFoundError(f"The file or URL ({url}) does not exist.")

    return None


def open_browser(
    url: str,
    path: str,
    params: str | list[str],
) -> None:

    if isinstance(params, str):
        commandLine = subprocess.list2cmdline([path])

        params = params.strip()
        if params:
            # Keep the raw command-line string so quoted parameter values are preserved.
            commandLine += f" {params}"

        commandLine += f" {subprocess.list2cmdline([url])}"

    else:
        commandLine = [path, *params, url]

    Log.debug(f"Start browser: {commandLine}")

    # Use LiberRPA Local Server to start the browser so the browser process is not tied to the RPA script process.
    subprocess.Popen(
        commandLine,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    return None


if __name__ == "__main__":
    ...
