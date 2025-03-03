# FileName: Basic.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


""" The Basic module should package the functions that be called without module name """
from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command


import time
import multiprocessing
import os

_boolHaveRecordVideo = False


@Log.trace(level="VERBOSE")
def delay(ms: int = 1000) -> None:
    """
    Delay a specific time.

    Parameters:
        ms: The milliseconds to delay.
    """
    Log.verbose(f"Delay {ms} ms.")
    time.sleep(ms / 1000)


@Log.trace()
def start_video_record() -> None:
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
        if multiprocessing.current_process().name == "MainProcess":
            send_command(
                eventName="record_command",
                command={"commandName": "video", "pid": os.getpid(), "folderName": Log.strLogFolder},
            )
            _boolHaveRecordVideo = True
        else:
            raise RuntimeError("Only the main process can start a video recording.")


if __name__ == "__main__":
    start_video_record()

    import time

    time.sleep(1)
    for i in range(0, 10, 1):
        time.sleep(1)
        print(i)
