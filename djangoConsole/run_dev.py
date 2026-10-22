# FileName: run_dev.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import logging
import os
import re
import signal
import subprocess
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import FrameType
from typing import BinaryIO, TextIO

_PATH_CONSOLE = Path(__file__).resolve().parent
_DICT_WORKER_COMMAND: dict[str, str] = {
    "email-worker": "run_email_worker",
    "job-worker": "run_job_worker",
    "scheduler": "run_scheduler",
    "backup-worker": "run_backup_worker",
}
# NOTE: Development retention is per service; the backup count excludes the current file.
_INT_LOG_MAX_BYTES = 50 * 1024 * 1024
_INT_LOG_BACKUP_COUNT = 9

_ANSI_RESET = "\x1b[0m"
_ANSI_GRAY = "\x1b[90m"
_ANSI_CYAN = "\x1b[36m"
_DICT_LEVEL_COLOR = {
    "DEBUG": _ANSI_GRAY,
    "INFO": "\x1b[32m",
    "WARNING": "\x1b[33m",
    "ERROR": "\x1b[31m",
    "CRITICAL": "\x1b[97;41m",
}
_DICT_STATUS_COLOR = {
    "1": _ANSI_CYAN,
    "2": _DICT_LEVEL_COLOR["INFO"],
    "3": _ANSI_CYAN,
    "4": _DICT_LEVEL_COLOR["WARNING"],
    "5": _DICT_LEVEL_COLOR["ERROR"],
}
# Keep this pattern aligned with the backend ConsoleFormatter output.
_RE_LOG_LINE = re.compile(
    r"(?P<time>\d{4}-\d{2}-\d{2}T\S+Z) "
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) "
    r"(?P<logger>\S+) (?P<request>request=\S+) (?P<message>.*)"
)
_RE_UVICORN_LEVEL = re.compile(r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)(?=:[ \t])")
_RE_HTTP_STATUS = re.compile(r"\bstatus=([1-5]\d{2})(?=[\s.]|$)")


def _enable_terminal_colors(stream: TextIO) -> bool:
    """Enable colors only on a supported terminal, using the standard library."""
    if not stream.isatty() or "NO_COLOR" in os.environ:
        return False

    if os.name != "nt":
        if os.environ.get("TERM", "") in ("", "dumb"):
            return False
        try:
            import curses
        except ImportError:
            return False
        try:
            curses.setupterm(fd=stream.fileno())
            return curses.tigetnum("colors") >= 8
        except (curses.error, OSError, ValueError):
            return False

    import ctypes
    import msvcrt
    from ctypes import wintypes

    try:
        consoleApi = ctypes.WinDLL("kernel32")
        getConsoleMode = consoleApi.GetConsoleMode
        getConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        getConsoleMode.restype = wintypes.BOOL
        setConsoleMode = consoleApi.SetConsoleMode
        setConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        setConsoleMode.restype = wintypes.BOOL
        consoleHandle = msvcrt.get_osfhandle(stream.fileno())
        consoleMode = wintypes.DWORD()
        if not getConsoleMode(consoleHandle, ctypes.byref(consoleMode)):
            return False
        # Preserve existing flags and enable processed output and ANSI sequences.
        return bool(setConsoleMode(consoleHandle, consoleMode.value | 0x0001 | 0x0004))
    except (OSError, ValueError):
        return False


def _color_log_message(message: str, level: str, *, colorHttpStatus: bool = False) -> str:
    messageColor = ""
    if level in ("WARNING", "ERROR"):
        messageColor = _DICT_LEVEL_COLOR[level]
    elif level == "CRITICAL":
        messageColor = _DICT_LEVEL_COLOR["ERROR"]

    if colorHttpStatus:
        message = _RE_HTTP_STATUS.sub(
            lambda matchObj: (
                f"{_DICT_STATUS_COLOR[matchObj[1][0]]}{matchObj[0]}"
                f"{_ANSI_RESET}{messageColor}"
            ),
            message,
        )
    return f"{messageColor}{message}{_ANSI_RESET}" if messageColor else message


class _TerminalFormatter(logging.Formatter):
    """Display local times and optional colors without changing captured file output."""

    def __init__(self, *, useColors: bool) -> None:
        super().__init__()
        self.useColors = useColors

    def format(self, record: logging.LogRecord) -> str:
        logLine = super().format(record)
        lineMatch = _RE_LOG_LINE.fullmatch(logLine)
        if lineMatch is not None:
            strLocalTime = (
                datetime
                .fromisoformat(lineMatch["time"])
                .astimezone()
                .isoformat(timespec="milliseconds")
            )
            if not self.useColors:
                return strLocalTime + logLine[lineMatch.end("time") :]

            level = lineMatch["level"]
            coloredMessage = _color_log_message(
                lineMatch["message"],
                level,
                colorHttpStatus=lineMatch["logger"] == "console.http",
            )
            return (
                f"{_ANSI_GRAY}{strLocalTime}{_ANSI_RESET} "
                f"{_DICT_LEVEL_COLOR[level]}{level}{_ANSI_RESET} "
                f"{_ANSI_CYAN}{lineMatch['logger']}{_ANSI_RESET} "
                f"{_ANSI_GRAY}{lineMatch['request']}{_ANSI_RESET} "
                f"{coloredMessage}"
            )

        if not self.useColors:
            return logLine

        levelMatch = _RE_UVICORN_LEVEL.match(logLine)
        if levelMatch is not None:
            level = levelMatch[1]
            coloredMessage = _color_log_message(logLine[levelMatch.end() :], level)
            return f"{_DICT_LEVEL_COLOR[level]}{level}{_ANSI_RESET}{coloredMessage}"
        return logLine


def _lock_log_file(lockFile: BinaryIO) -> None:
    """Keep one collector per service; the operating system releases the lock on exit."""
    if os.name == "nt":
        import msvcrt

        if lockFile.seek(0, os.SEEK_END) == 0:
            lockFile.write(b"0")
            lockFile.flush()
        lockFile.seek(0)
        msvcrt.locking(lockFile.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _keep_capturing(_signalNumber: int, _frame: FrameType | None) -> None:
    # Ctrl+C reaches the child through the shared terminal; keep collecting its shutdown output.
    pass


def _run_service(service: str, logger: logging.Logger) -> int:
    if service == "server":
        listCommand = [
            sys.executable,
            "-m",
            "uvicorn",
            "console_project.asgi:application",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--ws",
            "websockets-sansio",
            "--ws-max-size",
            "65536",  # 64 KiB; control messages contain no files or log batches.
            "--lifespan",
            "on",
            "--reload",
            "--reload-dir",
            str(_PATH_CONSOLE / "backend"),
            "--no-access-log",
            "--no-use-colors",
        ]
    else:
        listCommand = [
            sys.executable,
            "manage.py",
            _DICT_WORKER_COMMAND[service],
            "--no-color",
        ]

    previousHandler = signal.signal(signal.SIGINT, _keep_capturing)
    try:
        # Only this collector opens the log file, including while Uvicorn replaces its child.
        with subprocess.Popen(
            listCommand,
            cwd=_PATH_CONSOLE / "backend",
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            assert process.stdout is not None
            # Bound each captured fragment even if a diagnostic has no newline.
            while strOutput := process.stdout.readline(16 * 1024):
                logger.info(strOutput.rstrip("\r\n"))
            return process.wait()
    finally:
        if previousHandler is not None:
            signal.signal(signal.SIGINT, previousHandler)


def main() -> int:
    argumentParser = argparse.ArgumentParser(
        description="Run a Console development service with terminal output and rotating local logs."
    )
    argumentParser.add_argument("service", choices=("server", *_DICT_WORKER_COMMAND))
    arguments = argumentParser.parse_args()
    strService: str = arguments.service
    pathLogs = _PATH_CONSOLE / ".local/logs"
    pathLogs.mkdir(parents=True, exist_ok=True)
    pathLog = pathLogs / f"{strService}.log"

    with (pathLogs / f"{strService}.lock").open("a+b") as lockFile:
        try:
            _lock_log_file(lockFile)
        except OSError:
            print(
                f"Cannot lock {strService} logs. Stop its other development launcher before retrying.",
                file=sys.stderr,
            )
            return 1

        fileHandler = RotatingFileHandler(
            pathLog,
            maxBytes=_INT_LOG_MAX_BYTES,
            backupCount=_INT_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        terminalHandler = logging.StreamHandler(sys.stdout)
        terminalHandler.setFormatter(
            _TerminalFormatter(useColors=_enable_terminal_colors(sys.stdout))
        )
        logger = logging.Logger("console.dev", level=logging.INFO)
        logger.addHandler(fileHandler)
        logger.addHandler(terminalHandler)
        try:
            logger.info("Starting %s. Development log: %s", strService, pathLog)
            intExitCode = _run_service(strService, logger)
            logger.info("%s exited with code %s.", strService, intExitCode)
            return intExitCode
        finally:
            fileHandler.close()
            terminalHandler.close()


if __name__ == "__main__":
    raise SystemExit(main())
