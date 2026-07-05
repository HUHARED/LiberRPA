# FileName: _Application.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import StrPath

import subprocess
import win32con
import webbrowser
import urllib.parse
import os
from pathlib import Path
from typing import Literal


def run_application(filePath: StrPath, windowState: Literal["default", "maximize", "minimize"] = "default") -> int:
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

    process = subprocess.Popen([filePath], startupinfo=startupinfo, creationflags=subprocess.DETACHED_PROCESS)

    return process.pid


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
    subprocess.Popen(commandLine, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)

    return None


if __name__ == "__main__":
    ...
