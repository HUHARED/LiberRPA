# FileName: System.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import StrPath, DictComputerInfo

import winsound
from pathlib import Path
import sys
import os
import getpass
import platform


@Log.trace()
def play_sound(filePath: StrPath, wait: bool = True) -> None:
    """
    Play a WAV sound file.

    Only WAV files are supported because this function uses Windows winsound.PlaySound().
    MP3 and other formats are not supported.

    Parameters:
        filePath: The path to the WAV file to play. Accepts str or PathLike[str].
        wait: If True, waits until the sound finishes. If False, starts playing and returns immediately.
    """
    pathObj = Path(filePath)

    if not pathObj.is_file():
        raise FileNotFoundError(f"Sound file does not exist: {filePath}")

    if pathObj.suffix.lower() != ".wav":
        raise ValueError("Only WAV files are supported by System.play_sound().")

    flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
    if not wait:
        flags |= winsound.SND_ASYNC

    winsound.PlaySound(str(pathObj.resolve()), flags)


@Log.trace()
def get_environment_variable(name: str) -> str:
    """
    Get the value of an environment variable.

    Parameters:
        name: The name of the environment variable.

    Returns:
        str: The value of the environment variable.
    """
    value = os.environ.get(name)

    if value is None:
        raise ValueError(f"Environment variable '{name}' was not found.")

    return value


@Log.trace()
def set_environment_variable_temporarily(name: str, value: str) -> None:
    """
    Set an environment variable for the current process temporarily.

    This only affects the current process and child processes started after this variable is set. It does not change system-wide environment variables or environment variables of already running processes.

    Parameters:
        name: The name of the environment variable.
        value: The value to set.
    """
    os.environ[name] = value


@Log.trace()
def get_user_home_folder_path() -> str:
    """
    Get the home/profile folder path for the Windows account running this process.

    Returns:
        str: The home/profile folder path.
    """
    return str(Path.home())


@Log.trace()
def get_user_temp_folder_path() -> str:
    """
    Get the current user's temporary folder path.

    Returns:
        str: The current user's temporary folder path.
    """
    value = os.environ.get("TEMP")

    if value is None:
        raise ValueError("TEMP environment variable is not set.")

    if not Path(value).is_dir():
        raise FileNotFoundError(f"TEMP folder does not exist: {value}")

    return value


@Log.trace()
def get_computer_info() -> DictComputerInfo:
    """
    Get readable information about the current computer and Windows user.

    This function is intended for business logs, reports, and environment checks.
    The returned values can help users recognize which computer is running a process, but they should not be treated as secure or guaranteed-unique identifiers.

    Returns:
        DictComputerInfo: Readable computer and user information, including computer name, Windows user name, home folder path, temporary folder path, operating system, OS version, OS release, architecture, and machine type.
    """

    return {
        "computerName": platform.node(),
        "userName": getpass.getuser(),
        "homeFolderPath": get_user_home_folder_path(),
        "tempFolderPath": get_user_temp_folder_path(),
        "os": platform.system(),
        "osVersion": platform.version(),
        "osRelease": platform.release(),
        "architecture": platform.architecture()[0],
        "machine": platform.machine(),
    }


@Log.trace()
def exit() -> None:
    """
    End the current LiberRPA process.

    This function runs LiberRPA's process-ending logic first, then exits the
    Python process with exit code 0.
    """
    import liberrpa.FlowControl.End as End

    End.main()
    sys.exit(0)


if __name__ == "__main__":
    play_sound(filePath=R"C:\Program Files\Microsoft Office\root\Office16\MEDIA\CHIMES.WAV", wait=False)
    from time import sleep

    sleep(5)
