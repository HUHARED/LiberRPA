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
from dataclasses import dataclass
import re
import sys
from screeninfo import get_monitors
from screeninfo.common import Monitor

_RECORD_FRAME_RATE = 5
_DISPLAY_POLL_INTERVAL_SECONDS = 0.5
_DISPLAY_CHANGE_GRACE_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class _CaptureArea:
    x: int
    y: int
    width: int
    height: int


def _find_ffmpeg() -> str:
    if getattr(sys, "frozen", False):
        pathFfmpeg = Path(sys.executable).parent / "_internal" / "ffmpeg.exe"
    else:
        pathFfmpeg = Path(sys.prefix) / "Library" / "bin" / "ffmpeg.exe"

    if not pathFfmpeg.is_file():
        raise FileNotFoundError(f"FFmpeg executable was not found: {pathFfmpeg}")

    return str(pathFfmpeg)


_strFfmpegPath = _find_ffmpeg()


def _get_primary_screen() -> Monitor:
    primaryScreen = next((item for item in get_monitors() if item.is_primary), None)
    if not primaryScreen:
        raise RuntimeError("No primary monitor found.")

    if primaryScreen.width <= 0 or primaryScreen.height <= 0:
        raise RuntimeError(
            f"Invalid primary monitor size: {primaryScreen.width}x{primaryScreen.height}"
        )

    return primaryScreen


def _get_capture_area(
    primaryScreen: Monitor, initialWidth: int, initialHeight: int
) -> _CaptureArea:
    return _CaptureArea(
        x=primaryScreen.x,
        y=primaryScreen.y,
        width=min(primaryScreen.width, initialWidth),
        height=min(primaryScreen.height, initialHeight),
    )


def _start_record_part(
    folderName: str,
    partIndex: int,
    captureArea: _CaptureArea,
    outputWidth: int,
    outputHeight: int,
) -> tuple[subprocess.Popen, Path]:
    pathPart = Path(folderName).joinpath(f"video_record_part_{partIndex:04d}.mkv")

    command = [
        _strFfmpegPath,
        "-y",  # Overwrite output files without asking
        "-f",
        "gdigrab",  # Use gdigrab for screen capture
        "-framerate",
        str(_RECORD_FRAME_RATE),
        "-offset_x",
        str(captureArea.x),
        "-offset_y",
        str(captureArea.y),
        "-video_size",
        f"{captureArea.width}x{captureArea.height}",
        "-i",
        "desktop",  # Capture the desktop region
    ]

    if captureArea.width != outputWidth or captureArea.height != outputHeight:
        command.extend([
            "-vf",
            f"pad={outputWidth}:{outputHeight}:0:0:black",
        ])

    command.extend([
        "-c:v",
        "libx265",  # Use x265 codec, for a small size
        "-preset",
        "faster",  # Use a faster preset for reducing CPU usage, compress its size later.
        "-crf",
        "28",  # Set the default quality, compress later.
        str(pathPart),
    ])

    processRecord = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        # stderr=subprocess.PIPE wil cause ffmpeg can't stop.
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    return processRecord, pathPart


def _stop_ffmpeg(processRecord: subprocess.Popen) -> int:
    if processRecord.poll() is None:
        try:
            if processRecord.stdin:
                Log.debug("Sending 'q' to ffmpeg...")
                processRecord.stdin.write(b"q\n")
                processRecord.stdin.flush()
            else:
                Log.warning("Terminate ffmpeg.")
                processRecord.terminate()
        except OSError as e:
            if processRecord.poll() is None:
                Log.warning(
                    f"Failed to send quit command to ffmpeg: {e}. Terminating it."
                )
                processRecord.terminate()

    try:
        processRecord.wait(timeout=10)
    except subprocess.TimeoutExpired:
        Log.warning("ffmpeg did not stop after 10 seconds. Terminating it.")
        processRecord.terminate()

        try:
            processRecord.wait(timeout=5)
        except subprocess.TimeoutExpired:
            Log.warning("ffmpeg still did not stop. Killing it.")
            processRecord.kill()
            processRecord.wait()

    return processRecord.returncode


def _merge_record_parts(folderName: str, listPartPaths: list[Path]) -> bool:
    pathOutput = Path(folderName).joinpath("video_record.mkv")
    listValidPartPaths = [
        pathPart
        for pathPart in listPartPaths
        if pathPart.is_file() and pathPart.stat().st_size > 0
    ]

    if not listValidPartPaths:
        Log.error("No valid video recording part was created.")
        return False

    if pathOutput.is_file():
        pathOutput.unlink()

    if len(listValidPartPaths) == 1:
        listValidPartPaths[0].replace(pathOutput)
        return True

    pathConcatList = Path(folderName).joinpath("video_record_parts.txt")
    pathConcatList.write_text(
        "".join(f"file '{pathPart.name}'\n" for pathPart in listValidPartPaths),
        encoding="utf-8",
    )

    command = [
        _strFfmpegPath,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(pathConcatList),
        "-c",
        "copy",
        str(pathOutput),
    ]

    try:
        processCompleted = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    except Exception as e:
        Log.error(f"Failed to merge video recording parts: {e}")
        return False

    finally:
        if pathConcatList.is_file():
            pathConcatList.unlink()

    if processCompleted.returncode != 0:
        Log.warning(
            f"ffmpeg exit {processCompleted.returncode} when merging video recording parts."
        )
        Log.warning(processCompleted.stderr[-3000:])

        if pathOutput.is_file():
            pathOutput.unlink()

        return False

    for pathPart in listValidPartPaths:
        if pathPart.is_file():
            pathPart.unlink()

    return True


def record_screen(pid: int, folderName: str) -> None:

    primaryScreen = _get_primary_screen()
    initialWidth = primaryScreen.width
    initialHeight = primaryScreen.height
    captureArea = _get_capture_area(
        primaryScreen=primaryScreen,
        initialWidth=initialWidth,
        initialHeight=initialHeight,
    )

    processRecord: subprocess.Popen | None = None
    listPartPaths: list[Path] = []
    intPartIndex = 0
    boolRecordingFailed = False

    Log.debug(f"Record start: {folderName}")
    Log.debug(f"Record size: {initialWidth}x{initialHeight}")

    try:
        processRecord, pathPart = _start_record_part(
            folderName=folderName,
            partIndex=intPartIndex,
            captureArea=captureArea,
            outputWidth=initialWidth,
            outputHeight=initialHeight,
        )
        listPartPaths.append(pathPart)

        while psutil.pid_exists(pid):
            time.sleep(_DISPLAY_POLL_INTERVAL_SECONDS)

            try:
                primaryScreenCurrent = _get_primary_screen()
                captureAreaCurrent = _get_capture_area(
                    primaryScreen=primaryScreenCurrent,
                    initialWidth=initialWidth,
                    initialHeight=initialHeight,
                )
            except Exception as e:
                # Display information can be temporarily unavailable while Windows changes display modes.
                Log.debug(f"Could not query the primary monitor while recording: {e}")
                continue

            if captureAreaCurrent != captureArea:
                Log.info(
                    "Primary monitor capture area changed: "
                    f"{captureArea.x},{captureArea.y} {captureArea.width}x{captureArea.height} -> "
                    f"{captureAreaCurrent.x},{captureAreaCurrent.y} "
                    f"{captureAreaCurrent.width}x{captureAreaCurrent.height}. "
                    f"Keep recording output at {initialWidth}x{initialHeight}."
                )

                if processRecord.poll() is None:
                    _stop_ffmpeg(processRecord)
                else:
                    processRecord.wait()

                processRecord = None

                if not psutil.pid_exists(pid):
                    break

                captureArea = captureAreaCurrent
                intPartIndex += 1
                processRecord, pathPart = _start_record_part(
                    folderName=folderName,
                    partIndex=intPartIndex,
                    captureArea=captureArea,
                    outputWidth=initialWidth,
                    outputHeight=initialHeight,
                )
                listPartPaths.append(pathPart)
                continue

            if processRecord.poll() is not None:
                # gdigrab can fail just before Windows exposes the new monitor metrics.
                intReturnCode = processRecord.returncode
                time.sleep(_DISPLAY_CHANGE_GRACE_SECONDS)

                if not psutil.pid_exists(pid):
                    break

                try:
                    primaryScreenCurrent = _get_primary_screen()
                    captureAreaCurrent = _get_capture_area(
                        primaryScreen=primaryScreenCurrent,
                        initialWidth=initialWidth,
                        initialHeight=initialHeight,
                    )
                except Exception as e:
                    Log.warning(
                        f"ffmpeg stopped and the primary monitor is unavailable: {e}"
                    )
                    boolRecordingFailed = True
                    processRecord = None
                    break

                if captureAreaCurrent != captureArea:
                    Log.info(
                        "ffmpeg stopped during a display mode change. "
                        f"Restart recording at {captureAreaCurrent.width}x{captureAreaCurrent.height}, "
                        f"keeping output at {initialWidth}x{initialHeight}."
                    )

                    captureArea = captureAreaCurrent
                    intPartIndex += 1
                    processRecord, pathPart = _start_record_part(
                        folderName=folderName,
                        partIndex=intPartIndex,
                        captureArea=captureArea,
                        outputWidth=initialWidth,
                        outputHeight=initialHeight,
                    )
                    listPartPaths.append(pathPart)
                    continue

                Log.warning(f"ffmpeg exit {intReturnCode}.")
                boolRecordingFailed = True
                processRecord = None
                break

    except Exception as e:
        Log.error(f"Failed to start or continue recording: {e}")
        boolRecordingFailed = True

    finally:
        if processRecord is not None:
            intReturnCode = _stop_ffmpeg(processRecord)
            if intReturnCode != 0:
                Log.warning(f"ffmpeg exit {intReturnCode}.")
                boolRecordingFailed = True

    if boolRecordingFailed:
        Log.warning("Video recording did not complete successfully.")
        return

    if not _merge_record_parts(folderName=folderName, listPartPaths=listPartPaths):
        return

    Log.debug(f"Record end: {folderName} – clean exit.")
    # Add subtitle.
    _create_log_subtitle(folderName=folderName)
    _compress_video(folderName=folderName)


def _create_log_subtitle(folderName: str) -> None:
    strLogPath = str(Path(folderName).joinpath("human_read_MainProcess.log"))

    if not Path(strLogPath).is_file():
        Log.error("Log file not found, skipping subtitles.")
        return

    strSubtitlePath = str(Path(folderName).joinpath("video_record.srt"))

    strLogTotal = Path(strLogPath).read_text(encoding="utf-8")
    dictLogSeconds: dict[str, list[str]] = {}

    listEachLine = strLogTotal.split("\n")
    boolFoundSign = False

    for strLine in listEachLine:
        if not boolFoundSign:
            # Before save log, should find the start sign.
            if strLine.endswith(SIGN_START_RECORD_VIDEO):
                # print("Found sign.")
                boolFoundSign = True
                timeBase: datetime = datetime.strptime(
                    strLine[0:21], "[%Y-%m-%d %H:%M:%S]"
                )
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

    # print(dictLogSeconds)

    with open(file=strSubtitlePath, mode="w", encoding="utf-8") as fileObj:
        intIndex = 1
        for strTimestamp, listLog in dictLogSeconds.items():
            # Parse time for SRT format
            timeLog: datetime = datetime.strptime(strTimestamp, "[%Y-%m-%d %H:%M:%S]")
            timeOffset = (timeLog - timeBase).total_seconds()

            # Start time in HH:MM:SS,000 format
            timeStart = (datetime(1, 1, 1) + timedelta(seconds=timeOffset)).strftime(
                "%H:%M:%S,000"
            )
            # Show each log for 1 second
            timeEnd = (datetime(1, 1, 1) + timedelta(seconds=timeOffset + 1)).strftime(
                "%H:%M:%S,000"
            )

            # Write SRT entry
            fileObj.write(f"{intIndex}\n")
            fileObj.write(f"{timeStart} --> {timeEnd}\n")
            fileObj.write("\n".join(listLog) + "\n\n")

            intIndex += 1

    Log.debug("Create subtitle: " + strSubtitlePath)


def _compress_video(folderName: str) -> None:
    pathOriginal = Path(folderName).joinpath("video_record.mkv")
    pathTemp = Path(folderName).joinpath("video_record_temp.mkv")

    if not pathOriginal.is_file():
        Log.error(f"Original video not found: {str(pathOriginal)}")
        return

    # Users may change log folder, so add the checker.
    if pathTemp.is_file():
        pathTemp.unlink()

    command = [
        _strFfmpegPath,
        "-y",  # Overwrite output files without asking
        "-i",
        str(pathOriginal),
        "-map",
        "0:v:0",  # Use only the first video stream.
        "-c:v",
        "libx265",  # Use x265 codec, for a small size
        "-preset",
        "slow",  # Use a slow preset for reducing its size.
        "-crf",
        "38",  # Set the quality to a higher CRF value for smaller size
        str(pathTemp),
    ]

    # processCompleted: subprocess.CompletedProcess | None = None

    try:
        # Use subprocess.run() to wait it completed.
        processCompleted = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    except Exception as e:
        Log.error(f"Failed to compress video: {e}")
        return

    """ if processCompleted is None:
        Log.error("Failed to launch ffmpeg.")
        return """

    if processCompleted.returncode != 0:
        Log.warning(f"ffmpeg exit {processCompleted.returncode}.")
        Log.warning(processCompleted.stderr[-3000:])

        if pathTemp.is_file():
            pathTemp.unlink()

        return

    if not pathTemp.is_file():
        Log.error("ffmpeg compression finished, but temp video was not created.")
        return

    # GPT said bigger output file is possible.
    intOriginalSize = pathOriginal.stat().st_size
    intNewSize = pathTemp.stat().st_size

    Log.debug(f"Original size: {intOriginalSize}, compressed size: {intNewSize}")

    if intNewSize >= intOriginalSize:
        Log.warning("Compressed video is not smaller. Keep original video.")
        pathTemp.unlink()
        return

    pathTemp.replace(pathOriginal)
    Log.debug("Compressing done.")


if __name__ == "__main__":
    # print("Start.")
    # record_screen(pid=4100, folderName="./")
    # # time.sleep(5)
    # print("Done.")
    ...
