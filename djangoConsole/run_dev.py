# FileName: run_dev.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import logging
import os
import signal
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import FrameType
from typing import BinaryIO

_PATH_CONSOLE = Path(__file__).resolve().parent
# NOTE: Development retention is per service; the backup count excludes the current file.
_INT_LOG_MAX_BYTES = 50 * 1024 * 1024
_INT_LOG_BACKUP_COUNT = 9


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
            "--reload",
            "--reload-dir",
            str(_PATH_CONSOLE / "backend"),
            "--no-access-log",
            "--no-use-colors",
        ]
    else:
        listCommand = [sys.executable, "manage.py", "run_email_worker", "--no-color"]

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
    argumentParser.add_argument("service", choices=("server", "email-worker"))
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
