# FileName: _Record.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import SIGN_START_RECORD_VIDEO

import subprocess
import time
import psutil
from pathlib import Path
from datetime import datetime, timedelta
import re
import sys
from screeninfo import get_monitors


def _find_ffmpeg() -> str:
    if getattr(sys, "frozen", False):
        # When it packaged by pyinstaller, ffmpeg.exe may can't be found, so handle it.
        return str(Path(sys.executable).parent / "_internal/ffmpeg.exe")
    else:
        return "ffmpeg"


strFfmpegPath = _find_ffmpeg()
Log.info(f"strFfmpegPath={strFfmpegPath}")


def record_screen(pid: int, folderName: str) -> None:

    # Find primary monitor
    primaryScreen = next((item for item in get_monitors() if item.is_primary), None)
    if not primaryScreen:
        raise RuntimeError("No primary monitor found.")

    processRecord: subprocess.Popen | None = None
    Log.debug(f"Record start: {folderName}")
    try:

        command = [
            strFfmpegPath,
            "-y",  # Overwrite output files without asking
            "-f",
            "gdigrab",  # Use gdigrab for screen capture
            "-framerate",
            "5",  # Set frame rate to 5 fps, for a small size
            "-offset_x",
            str(primaryScreen.x),
            "-offset_y",
            str(primaryScreen.y),
            "-video_size",
            f"{primaryScreen.width}x{primaryScreen.height}",
            "-i",
            "desktop",  # Capture the entire desktop
            "-vcodec",
            "libx265",  # Use x265 codec, for a small size
            "-preset",
            "medium",  # Use a medium preset for balancing CPU usage and size
            "-crf",
            "38",  # Set the quality to a higher CRF value for smaller size
            str(Path(folderName).joinpath("video_record.mkv")),  # Save the output as a single MKV file
        ]

        processRecord = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            # stderr=subprocess.PIPE wil cause ffmpeg can't stop.
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # Monitor both the ffmpeg process and the external PID
        while psutil.pid_exists(pid):
            time.sleep(2)

    except Exception as e:
        Log.error(f"Failed to start recording: {e}")
        return

    finally:

        if processRecord is None:
            Log.error("Failed to launch ffmpeg — skipping cleanup.")
            return

        # Politely tell ffmpeg to quit
        if processRecord.stdin:
            Log.debug("Sending 'q' to ffmpeg...")
            processRecord.stdin.write(b"q\n")
            processRecord.stdin.flush()
        else:
            Log.warning("Teminate ffmpeg.")
            processRecord.terminate()

        processRecord.wait(timeout=10)

        if processRecord.returncode == 0:
            Log.debug(f"Record end: {folderName} – clean exit.")
            # Add subtitle.
            _create_log_subtitle(folderName=folderName)
        else:
            Log.warning(f"ffmpeg exit {processRecord.returncode}.")


def _create_log_subtitle(folderName: str) -> None:
    strLogPath = str(Path(folderName).joinpath("human_read_MainProcess.log"))

    if Path(strLogPath).is_file() == False:
        Log.error("Log file not found, skipping subtitles.")
        return

    strSubtilePath = str(Path(folderName).joinpath("video_record.srt"))

    strLogTotal = Path(strLogPath).read_text()
    dictLogSeconds: dict[str, list[str]] = {}

    listEachLine = strLogTotal.split("\n")
    boolFoundSign = False

    for strLine in listEachLine:
        if boolFoundSign == False:
            # Before save log, should find the start sign.
            if strLine.endswith(SIGN_START_RECORD_VIDEO):
                # print("Found sign.")
                boolFoundSign = True
                timeBase: datetime = datetime.strptime(strLine[0:21], "[%Y-%m-%d %H:%M:%S]")
                continue
        else:
            # Have found sign, add log to dictionary
            strTime = strLine[0:21]
            if not re.fullmatch(R"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", strTime):
                # The line has no time text, continue.
                continue
            if dictLogSeconds.get(strTime) is None:
                # Limit the length of each line to avoid overwhelming video
                dictLogSeconds[strTime] = [strLine[0:120]]
            else:
                # This second has some log. Only save 3 log.
                if len(dictLogSeconds[strTime]) >= 3:
                    continue
                else:
                    dictLogSeconds[strTime].append(strLine[0:120])

    if not boolFoundSign:
        Log.error("Not found SIGN_START_RECORD_VIDEO.")
        return None

    print(dictLogSeconds)

    with open(file=strSubtilePath, mode="w", encoding="utf-8") as fileObj:
        intIndex = 1
        for strTimestamp, listLog in dictLogSeconds.items():
            # Parse time for SRT format
            timeLog: datetime = datetime.strptime(strTimestamp, "[%Y-%m-%d %H:%M:%S]")
            timeOffset = (timeLog - timeBase).total_seconds()

            # Start time in HH:MM:SS,000 format
            timeStart = (datetime(1, 1, 1) + timedelta(seconds=timeOffset)).strftime("%H:%M:%S,000")
            # Show each log for 1 second
            timeEnd = (datetime(1, 1, 1) + timedelta(seconds=timeOffset + 1)).strftime("%H:%M:%S,000")

            # Write SRT entry
            fileObj.write(f"{intIndex}\n")
            fileObj.write(f"{timeStart} --> {timeEnd}\n")
            fileObj.write("\n".join(listLog) + "\n\n")

            intIndex += 1

    Log.debug("Create subtitle: " + strSubtilePath)


if __name__ == "__main__":
    # print("Start.")
    # record_screen(pid=4100, folderName="./")
    # # time.sleep(5)
    # print("Done.")
    _create_log_subtitle(folderName=R"C:\Users\huhar\Documents\LiberRPA\Editor\OutputLog\library\2024-10-18_143922")
