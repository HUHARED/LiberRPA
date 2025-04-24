# FileName: System.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import winsound
import sys
import os
import re
import subprocess


@Log.trace()
def play_sound(soundPath: str) -> None:
    """
    Plays a sound file specified by the soundPath parameter using the Windows Sound API.
    Only support waveform audio files (WAV).
    """
    if not os.path.isfile(soundPath):
        raise FileNotFoundError(f"Sound file '{soundPath}' not found.")
    winsound.PlaySound(sound=soundPath, flags=winsound.SND_FILENAME)


@Log.trace()
def get_environment_variable(name: str) -> str:
    value = os.environ.get(name)

    if value is None:
        raise ValueError(f"Not found the environment named '{name}'")
    return value


@Log.trace()
def set_environment_variable_temporarily(name: str, value: str) -> None:
    """
    It only affects the environment variables of the current process (and any child processes spawned by it after the variable is set).

    It does not change the environment variables system-wide or for other processes running.
    """
    os.environ[name] = value


@Log.trace()
def get_user_home_folder_path() -> str:
    return os.environ.get("USERPROFILE", "N/A")


@Log.trace()
def get_user_temp_folder_path() -> str:
    value = os.environ.get("TEMP")

    if value is None:
        raise ValueError("TEMP environment variable is not set or TEMP folder does not exist.")

    return str(value)


@Log.trace()
def get_windows_product_id() -> str:
    """
    Unique to each Windows installation but can change with major system updates or reinstallation.

    Returns:
        str: The product id.
    """
    result = subprocess.run("wmic os get SerialNumber", capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError("Failed to retrieve Windows Product ID.")

    match = re.search(r"([A-Z0-9]+-)+([A-Z0-9]+)", result.stdout)

    if match is None:
        raise ValueError("Failed to extract a valid Windows Product ID.")

    return match.group()


@Log.trace()
def exit() -> None:
    import liberrpa.FlowControl.End as End

    End.main()
    sys.exit(0)


if __name__ == "__main__":
    # print(get_windows_product_id())

    # print(os.environ.get("USERPROFILE", "N/A"))
    # exit()
    play_sound(soundPath=R"G:\OneDrive\Workspace\LiberRPA_ProjectTest\all_modules_test\success.mp3")
