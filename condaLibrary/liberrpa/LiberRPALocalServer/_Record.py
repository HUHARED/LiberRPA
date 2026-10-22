# FileName: _Record.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import SIGN_START_RECORD_VIDEO

import subprocess
import msvcrt
import time
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import StrEnum
import json
import re
import sys
from screeninfo import get_monitors
from screeninfo.common import Monitor

_RECORD_FRAME_RATE = 5
_RECORD_PRESET = "faster"
_RECORD_CRF = 38
_MAX_RECORD_CPU_COUNT = 4
_DISPLAY_POLL_INTERVAL_SECONDS = 0.5
_DISPLAY_CHANGE_GRACE_SECONDS = 1.0


class _RecordingStatus(StrEnum):
    RECORDING = "recording"
    PROCESSING = "processing"
    READY = "ready"
    UNAVAILABLE = "unavailable"


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


def _set_record_process_resources(processRecord: subprocess.Popen) -> None:
    try:
        listAvailableCpu = psutil.Process().cpu_affinity()
        if not listAvailableCpu:
            raise RuntimeError("No available logical CPU was reported for Local Server.")

        intRecordCpuCount = max(
            1,
            min(_MAX_RECORD_CPU_COUNT, len(listAvailableCpu) // 2),
        )
        listRecordCpu = listAvailableCpu[-intRecordCpuCount:]
        psutil.Process(processRecord.pid).cpu_affinity(listRecordCpu)
        Log.debug(
            f"Set ffmpeg CPU affinity to {listRecordCpu} from {len(listAvailableCpu)} available logical CPUs."
        )
    except Exception as e:
        Log.warning(f"Failed to limit ffmpeg CPU affinity: {e}")


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
        _RECORD_PRESET,  # Keep recording CPU usage low enough for the automation workload.
        "-crf",
        str(_RECORD_CRF),  # Record directly at the final diagnostic-video quality.
        str(pathPart),
    ])

    processRecord = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        # stderr=subprocess.PIPE wil cause ffmpeg can't stop.
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
        | subprocess.BELOW_NORMAL_PRIORITY_CLASS,
    )
    _set_record_process_resources(processRecord=processRecord)

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

    pathSubtitleTemp = Path(strSubtitlePath + ".tmp")
    with pathSubtitleTemp.open(mode="w", encoding="utf-8") as fileObj:
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

    pathSubtitleTemp.replace(strSubtitlePath)
    Log.debug("Create subtitle: " + strSubtitlePath)


def record_screen(pid: int, folderName: str) -> None:
    def write_state(status: _RecordingStatus, reason: str = "") -> None:
        dictState: dict[str, str | int | None] = {
            "status": status,
            "videoSizeBytes": None,
            "subtitleSizeBytes": None,
            "reason": reason
            .replace("\0", "")
            .encode("utf-8", errors="replace")
            .decode("utf-8")[:2000],
        }
        pathState = Path(folderName) / "video_record.state.json"
        pathTemp = pathState.with_suffix(".tmp")
        try:
            if status == _RecordingStatus.READY:
                for strKey, strName in (
                    ("videoSizeBytes", "video_record.mkv"),
                    ("subtitleSizeBytes", "video_record.srt"),
                ):
                    pathFile = Path(folderName) / strName
                    if pathFile.is_file() and (intSize := pathFile.stat().st_size) > 0:
                        dictState[strKey] = intSize
            pathTemp.write_text(
                json.dumps(dictState, ensure_ascii=False), encoding="utf-8"
            )
            pathTemp.replace(pathState)
        except OSError as e:
            Log.error(f"Could not save recording state: {e}")

    def record() -> None:
        processRecord: subprocess.Popen | None = None
        listPartPaths: list[Path] = []
        intPartIndex = 0
        boolRecordingFailed = False

        write_state(_RecordingStatus.RECORDING)
        try:
            primaryScreen = _get_primary_screen()
            initialWidth = primaryScreen.width
            initialHeight = primaryScreen.height
            captureArea = _get_capture_area(
                primaryScreen=primaryScreen,
                initialWidth=initialWidth,
                initialHeight=initialHeight,
            )

            Log.debug(f"Record start: {folderName}")
            Log.debug(f"Record size: {initialWidth}x{initialHeight}")

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
                        f"Primary monitor capture area changed: {captureArea.x},{captureArea.y} {captureArea.width}x{captureArea.height} -> {captureAreaCurrent.x},{captureAreaCurrent.y} {captureAreaCurrent.width}x{captureAreaCurrent.height}. "
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
                            f"Restart recording at {captureAreaCurrent.width}x{captureAreaCurrent.height}, keeping output at {initialWidth}x{initialHeight}."
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
                try:
                    intReturnCode = _stop_ffmpeg(processRecord)
                    if intReturnCode != 0:
                        Log.warning(f"ffmpeg exit {intReturnCode}.")
                        boolRecordingFailed = True
                except Exception as e:
                    Log.error(f"Failed to stop recording: {e}")
                    boolRecordingFailed = True

        if boolRecordingFailed:
            write_state(
                _RecordingStatus.UNAVAILABLE,
                "Video recording did not complete successfully.",
            )
            return

        write_state(_RecordingStatus.PROCESSING)
        try:
            if not _merge_record_parts(
                folderName=folderName, listPartPaths=listPartPaths
            ):
                write_state(
                    _RecordingStatus.UNAVAILABLE,
                    "The recorded video could not be assembled.",
                )
                return
        except Exception as e:
            Log.error(f"Failed to assemble the recording: {e}")
            write_state(
                _RecordingStatus.UNAVAILABLE, "The recorded video could not be assembled."
            )
            return

        strReason = ""
        try:
            _create_log_subtitle(folderName=folderName)
        except Exception as e:
            Log.error(f"Failed to create recording subtitles: {e}")
            strReason = "Subtitles could not be created."
        write_state(_RecordingStatus.READY, strReason)
        Log.debug(f"Record end: {folderName} – clean exit.")

    pathLock = Path(folderName) / "video_record.lock"
    # NOTE: Executor probes this byte lock; keep it held until all recording work has ended.
    with pathLock.open("a+b") as fileLock:
        if fileLock.tell() == 0:
            fileLock.write(b"1")
            fileLock.flush()
        fileLock.seek(0)
        msvcrt.locking(fileLock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            record()
        except BaseException:
            write_state(_RecordingStatus.UNAVAILABLE, "Video recording was interrupted.")
            raise
        finally:
            fileLock.seek(0)
            msvcrt.locking(fileLock.fileno(), msvcrt.LK_UNLCK, 1)
