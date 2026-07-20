# FileName: Basic.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


""" The Basic module should package the functions that be called without module name """
from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command
from liberrpa.Common._Utils import PROCESS_NAME
from liberrpa.Common._TypedValue import StrPath


import time
import os
from pathlib import Path
import sys

_boolHaveRecordVideo = False


@Log.trace(level="VERBOSE")
def delay(ms: int = 1000) -> None:
    """
    Wait for a specified time, in milliseconds.

    Parameters:
        ms: The milliseconds to delay.
    """
    Log.verbose(f"Delay {ms} ms.")
    time.sleep(ms / 1000)


def _get_component_package_root() -> Path:
    frame = sys._getframe(1)

    try:
        while frame is not None:
            moduleFile = frame.f_globals.get("__file__")

            if isinstance(moduleFile, str):
                pathModule = Path(moduleFile).resolve()

                for pathParent in pathModule.parents:
                    if pathParent.name == "src":
                        pathProject = pathParent.parent

                        if (pathProject / "component.json").is_file():
                            pathRelative = pathModule.relative_to(pathParent)

                            if len(pathRelative.parts) >= 2:
                                pathPackage = pathParent / pathRelative.parts[0]

                                if pathPackage.is_dir() and (pathPackage / "__init__.py").is_file():
                                    return pathPackage

                    elif pathParent.name == "_Components":
                        pathProject = pathParent.parent

                        if (pathProject / "flow.json").is_file() or (pathProject / "component.json").is_file():
                            pathRelative = pathModule.relative_to(pathParent)

                            if len(pathRelative.parts) >= 2:
                                pathPackage = pathParent / pathRelative.parts[0]

                                if pathPackage.is_dir() and (pathPackage / "__init__.py").is_file():
                                    return pathPackage

            frame = frame.f_back

    finally:
        del frame

    raise RuntimeError(
        "Failed to determine the current Component package. "
        "This function must be called from code inside a LiberRPA Component package."
    )


@Log.trace()
def get_component_resource_path(relativePath: StrPath) -> str:
    """
    Get the absolute path of a resource in the current Component package.

    The resource path is resolved relative to the top-level Component package, whether the Component is running in its development project or has been imported into another Project.

    Parameters:
        relativePath: The resource path relative to the Component package root. Accepts str or PathLike[str].

    Returns:
        str: The absolute path of the resource.

    Examples:
        get_component_resource_path("_Templates/default.xlsx")
        get_component_resource_path("_Config")
    """
    pathRelative = Path(relativePath)

    if pathRelative.is_absolute():
        raise ValueError("relativePath must be a relative path.")

    if not pathRelative.parts:
        raise ValueError("relativePath can't be empty.")

    if ".." in pathRelative.parts:
        raise ValueError("relativePath can't contain '..'.")

    pathPackage = _get_component_package_root()
    pathResource = (pathPackage / pathRelative).resolve()

    if not pathResource.is_relative_to(pathPackage):
        raise ValueError("relativePath must remain inside the Component package.")

    if not pathResource.exists():
        raise FileNotFoundError(f"Component resource not found: '{pathRelative}'. Component package: '{pathPackage}'.")

    return str(pathResource)


@Log.trace()
def _start_video_record() -> None:
    """
    Start the video recording.

    Only work if it's the main process and first executed.
    """
    global _boolHaveRecordVideo
    # Only record once in each running.
    if _boolHaveRecordVideo:
        Log.warning("The process has started a video recording.")
    else:
        # Only the main process can start the record.
        if PROCESS_NAME == "MainProcess":
            send_command(
                eventName="record_command",
                command={"commandName": "video", "pid": os.getpid(), "folderName": Log.strLogFolder},
            )
            _boolHaveRecordVideo = True
        else:
            raise RuntimeError("Only the main process can start a video recording.")


if __name__ == "__main__":
    _start_video_record()

    import time

    time.sleep(1)
    for i in range(0, 10, 1):
        time.sleep(1)
        print(i)
