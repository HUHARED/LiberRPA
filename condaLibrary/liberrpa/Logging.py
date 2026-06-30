# FileName: Logging.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""
This module intentionally initializes project context and logger on import.
It is expected to be imported at RPA project startup.
"""
import liberrpa.Common._Initialization  # noqa: F401  # Import for LiberRPA project initialization side effects.

from liberrpa.Common._Utils import (
    PATH_PROJECT_ROOT,
    STR_PROJECT_ROOT,
    PATH_PROJECT_JSON,
    PATH_PROJECT_FLOW,
    PROCESS_NAME,
)
from liberrpa.Common._BasicConfig import get_basic_config_dict, get_liberrpa_folder_path
from liberrpa.Common._Exception import get_exception_info

import os
import getpass
import io
import traceback
from pathlib import Path
from uuid import uuid4
import json5
import json
import re
import socket
from logging.handlers import RotatingFileHandler
import logging
import sys
from functools import wraps
import ctypes
from pathvalidate import sanitize_filepath
from typing import Any, Literal

VERBOSE_LEVEL_NUM = 5
logging.addLevelName(VERBOSE_LEVEL_NUM, "VERBOSE")
type LogLevel = Literal["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


_SET_BUILTIN_KEY = {
    "timestamp",
    "level",
    "message",
    "userName",
    "machineName",
    "processName",
    "fileName",
    "lineNo",
    "projectName",
    "logId",
}
_SET_BUILTIN_KEY.update(set(logging.makeLogRecord({}).__dict__.keys()))
# {'msg', 'levelname', 'exc_info', 'thread', 'threadName', 'name', 'process', 'funcName', 'args', 'pathname', 'taskName', 'levelno', 'lineno', 'msecs', 'created', 'filename', 'module', 'relativeCreated', 'exc_text', 'processName', 'stack_info'}

_SET_INTERNAL_FILE = {
    "Logging.py",
    "Run.py",
    "End.py",
    "ProjectFlowInit.py",
    "_UiElement.py",
    "_WebSocket.py",
    "Trigger.py",
}


def _find_caller(stack_info=False, stacklevel=2):
    """
    Find the stack frame of the caller so that we can note the source file name, line number, and function name.
    """
    f = logging.currentframe()
    if f is not None:
        for _ in range(stacklevel):
            if f is None:
                break
            f = f.f_back  # type: ignore
    rv = "(unknown file)", 0, "(unknown function)", None
    if f is not None:
        co = f.f_code
        sinfo = None
        if stack_info:
            sio = io.StringIO()  # type: ignore
            sio.write("Stack (most recent call last):\n")
            traceback.print_stack(f, file=sio)  # type: ignore
            sinfo = sio.getvalue()
            if sinfo[-1] == "\n":
                sinfo = sinfo[:-1]
            sio.close()
        rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
    return rv


class ConditionalHumanReadFormatter(logging.Formatter):
    def __init__(self, normalFmt: str, internalFmt: str, datefmt: str):
        super().__init__()
        self.normalFormatter = logging.Formatter(normalFmt, datefmt=datefmt)
        self.internalFormatter = logging.Formatter(internalFmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        # Not record [%(filename)s][%(lineno)d] in human-read log if the filnename is "Logging.py" and so on, to make the log more concise.
        if record.filename in _SET_INTERNAL_FILE:
            return self.internalFormatter.format(record)
        return self.normalFormatter.format(record)


class JsonLineFormatter(logging.Formatter):
    def __init__(self, projectName: str, customLogPartDict: dict[str, str]):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.projectName = projectName
        self.customLogPartDict = customLogPartDict
        self.userName = getpass.getuser()
        self.machineName = socket.gethostname()

    def _get_serializable_obj_or_str(self, value: Any) -> Any:
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False)
            return value
        except (TypeError, ValueError):
            return repr(value)

    def format(self, record: logging.LogRecord) -> str:
        dictData = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": self._get_serializable_obj_or_str(record.msg),
            "userName": self.userName,
            "machineName": self.machineName,
            "processName": record.processName,
            "fileName": record.filename,
            "lineNo": record.lineno,
            "projectName": self.projectName,
            "logId": str(uuid4()),
        }

        for key in self.customLogPartDict:
            dictData[key] = getattr(record, key, self.customLogPartDict[key])

        return json.dumps(dictData, ensure_ascii=False, allow_nan=False)


class ColoredConsoleFormatter(logging.Formatter):
    RESET = "\033[0m"

    LEVEL_STYLES = {
        "VERBOSE": "\033[2m",  # dim
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[1;33m",  # bold yellow
        "ERROR": "\033[1;31m",  # bold red
        "CRITICAL": "\033[1;37;41m",  # bold white on red background
    }

    FIELD_STYLES = {
        "timestamp": "\033[2m",  # dim
        "processName": "\033[35m",  # magenta
        "fileName": "\033[34m",  # blue
        "lineNo": "\033[33m",  # yellow
        "custom": "\033[36m",  # cyan
    }

    TOKEN_STYLES = {
        "string": "\033[32m",  # green
        "number": "\033[35m",  # magenta
        "keyword": "\033[1;35m",  # bold magenta
    }
    TOKEN_RE = re.compile(
        r"(?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
        r"|(?P<keyword>\b(?:true|false|null|True|False|None)\b)"
        r"|(?P<number>(?<![\w.])-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.]))"
    )

    def __init__(self, datefmt: str, customLogPart: list[str] | None = None) -> None:
        super().__init__(datefmt=datefmt)
        self.listCustomLogPart = customLogPart or []

    def _generate_color_text(self, text: object, style: str) -> str:
        text = str(text)

        if not style:
            return text

        return f"{style}{text}{self.RESET}"

    def _wrap_by_bracket_and_generate_color(self, text: object, style: str) -> str:
        return self._generate_color_text(f"[{text}]", style)

    def _highlight_message_tokens(self, text: str) -> str:

        def replace(match: re.Match[str]) -> str:
            kind = match.lastgroup
            value = match.group(0)

            if kind == "string":
                return self._generate_color_text(value, self.TOKEN_STYLES["string"])

            if kind == "number":
                return self._generate_color_text(value, self.TOKEN_STYLES["number"])

            if kind == "keyword":
                return self._generate_color_text(value, self.TOKEN_STYLES["keyword"])

            return value

        return self.TOKEN_RE.sub(replace, text)

    def _highlight_trace(self, text: str) -> str:
        return self._generate_color_text(text, "\033[3;36m")  # italic cyan

    def format(self, record: logging.LogRecord) -> str:
        strTimestamp = self.formatTime(record, self.datefmt)
        strLevel = record.levelname

        listParts: list[str] = [
            self._wrap_by_bracket_and_generate_color(strTimestamp, self.FIELD_STYLES["timestamp"]),
            self._wrap_by_bracket_and_generate_color(strLevel, self.LEVEL_STYLES.get(strLevel, "")),
        ]

        if record.processName != "MainProcess":
            listParts.append(
                self._wrap_by_bracket_and_generate_color(record.processName, self.FIELD_STYLES["processName"])
            )

        if record.filename not in _SET_INTERNAL_FILE:
            listParts.append(self._wrap_by_bracket_and_generate_color(record.filename, self.FIELD_STYLES["fileName"]))
            listParts.append(self._wrap_by_bracket_and_generate_color(record.lineno, self.FIELD_STYLES["lineNo"]))

        for name in self.listCustomLogPart:
            value = getattr(record, name, "")
            listParts.append(self._wrap_by_bracket_and_generate_color(value, self.FIELD_STYLES["custom"]))

        message = record.getMessage()
        if message.startswith("START:") or message.startswith("END  :"):
            message = self._highlight_trace(message)
        else:
            message = self._highlight_message_tokens(message)

        result = "".join(listParts) + " " + message

        return result


class Logger:
    def __init__(self) -> None:
        self.dictBasicConfig = get_basic_config_dict()
        self.dictCustomLogPart: dict[str, str] = {}
        self.dictLevel = {
            "VERBOSE": VERBOSE_LEVEL_NUM,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        # Creates a time-based folder for logs specific to the current project.

        dictProject: dict[str, Any] = json5.loads(PATH_PROJECT_JSON.read_text(encoding="utf-8"))  # type: ignore

        strLogFolderName = os.getenv("LogFolderName")
        if strLogFolderName is not None:
            self.strProjectName = strLogFolderName
            print("Set log folder name:", strLogFolderName)

        elif dictProject.get("executorPackage"):
            # Executor package's name is not the project name, use data in project.json
            self.strProjectName = dictProject["executorPackageName"]

        else:
            self.strProjectName = os.path.basename(STR_PROJECT_ROOT)

        # If it's an Executor package, add version subfolder.
        if dictProject.get("executorPackage"):
            try:
                dictExecutorConfig: dict[str, str] = json5.loads(
                    Path(os.path.join(get_liberrpa_folder_path(), "./configFiles/Executor.jsonc")).read_text()
                )  # type: ignore

                strProjectLogFolderPath = dictExecutorConfig.get("projectLogFolderPath", "")

                if strProjectLogFolderPath != "":
                    self.strLogFolder = sanitize_filepath(
                        os.path.join(
                            strProjectLogFolderPath,
                            self.strProjectName,
                            dictProject["executorPackageVersion"],
                            dictProject["lastStartUpTime"],
                        )
                    )
                else:
                    self.strLogFolder = sanitize_filepath(
                        os.path.join(
                            self.dictBasicConfig["outputLogPath"],
                            self.strProjectName,
                            dictProject["executorPackageVersion"],
                            dictProject["lastStartUpTime"],
                        )
                    )
            except Exception as e:
                raise Exception(f"Error in handle Executor file: {e}")
        else:
            self.strLogFolder = sanitize_filepath(
                os.path.join(
                    self.dictBasicConfig["outputLogPath"],
                    self.strProjectName,
                    dictProject["lastStartUpTime"],
                )
            )

        # Update project.json, add "logPath" for other parts to use later. Such as screen recording, screenshots.

        # All processes create the folder to avoid a subprocess writes file before MainProcess.
        os.makedirs(self.strLogFolder, exist_ok=True)

        # Only the MainProcess can initialize project.json.
        if PROCESS_NAME == "MainProcess":
            dictProject["logPath"] = self.strLogFolder
            dictProject["executorPackageStatus"] = "running"
            strTemp = json.dumps(dictProject, indent=4, ensure_ascii=False, allow_nan=False)

            # Avoid the situation that MainProcess was killed accidently and created a incompleted file.
            pathTemp = PATH_PROJECT_ROOT / "project.json.tmp"
            pathTemp.write_text(data=strTemp, encoding="utf-8", errors="strict")
            pathTemp.replace(PATH_PROJECT_JSON)
            print("Update project.json: " + strTemp)

        # Create loggers
        self.colorfulConsoleHandlerObj = logging.StreamHandler(stream=sys.stderr)  # Console handler
        self.humanLogger = self._create_logger(f"human_read_{PROCESS_NAME}.log", humanReadable=True)
        self.humanLogger.addHandler(self.colorfulConsoleHandlerObj)  # Add the StreamHandler to human_logger
        self.machineLogger = self._create_logger(fileName=f"machine_read_{PROCESS_NAME}.jsonl", humanReadable=False)

    def _create_logger(self, fileName: str, humanReadable: bool) -> logging.Logger:
        logger = logging.getLogger(fileName)

        # Avoid multiple processes if its imported or reloaded multiple times.

        # Use [:] to create duplicate.
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        logger.handlers.clear()
        logger.propagate = False

        logger.setLevel(logging.DEBUG)

        strLogFilePath = os.path.join(self.strLogFolder, fileName)
        fileHandlerObj = RotatingFileHandler(strLogFilePath, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")

        if humanReadable:
            formatter = self._get_human_formatter()
            self.colorfulConsoleHandlerObj.setFormatter(self._get_console_formatter())
        else:
            formatter = self._get_json_formatter()

        fileHandlerObj.setFormatter(formatter)
        logger.addHandler(fileHandlerObj)

        logger.findCaller = _find_caller
        return logger

    def _build_human_format(self, includeSource: bool) -> str:
        listParts: list[str] = [
            "%(asctime)s",
            "%(levelname)s",
        ]

        # Not show processName in MainProcess to make log more concise.
        if PROCESS_NAME != "MainProcess":
            listParts.append("%(processName)s")

        if includeSource:
            listParts.extend(
                [
                    "%(filename)s",
                    "%(lineno)d",
                ]
            )

        for key in self.dictCustomLogPart:
            listParts.append(f"%({key})s")

        return "".join(f"[{part}]" for part in listParts) + " %(message)s"

    def _get_human_formatter(self) -> logging.Formatter:
        fmtNormal = self._build_human_format(includeSource=True)
        fmtInternal = self._build_human_format(includeSource=False)

        return ConditionalHumanReadFormatter(
            normalFmt=fmtNormal,
            internalFmt=fmtInternal,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def _get_console_formatter(self) -> logging.Formatter:
        return ColoredConsoleFormatter(
            datefmt="%Y-%m-%d %H:%M:%S",
            customLogPart=list(self.dictCustomLogPart.keys()),
        )

    def _get_json_formatter(self) -> logging.Formatter:
        return JsonLineFormatter(
            projectName=self.strProjectName,
            customLogPartDict=self.dictCustomLogPart,
        )

    def _get_custom_log_parts(self) -> dict[str, str]:
        # Evaluate custom log parts and return them
        dictParts: dict[str, str] = {}
        for key, value in self.dictCustomLogPart.items():
            dictParts[key] = value
        return dictParts

    def _refresh_loggers_format(self) -> None:
        # Refresh format for both loggers

        self.humanLogger.handlers[0].setFormatter(self._get_human_formatter())
        self.colorfulConsoleHandlerObj.setFormatter(self._get_console_formatter())
        self.machineLogger.handlers[0].setFormatter(self._get_json_formatter())

        if len(self.humanLogger.handlers) > 1 and isinstance(self.humanLogger.handlers[1], logging.StreamHandler):
            self.humanLogger.handlers[1].setFormatter(self._get_console_formatter())

    def add_custom_log_part(self, name: str, text: str):
        """
        Adds a new part to the log entry format.

        If the name already exists, the text will be updated.

        The name cannot be one of the reserved keywords(["timestamp", "level", "message", "userName", "machineName", "processName", "fileName", "lineNo", "projectName", "logId"]) due to they are used in machine_read log.

        Parameters:
            name: The new part's name to be added. This will be a new key in the machine_read log entry, but the name won't show in human_read log.
            text: The text of the new log part, which will be displayed in human_read log.
        """

        # Non-string text will be converted to string automatically.

        if name in _SET_BUILTIN_KEY:
            raise ValueError(
                f"The argumnent 'name'({name}) cann't be one of {_SET_BUILTIN_KEY}, it has been used in machine_read log."
            )
        if not name.isidentifier():
            raise ValueError("custom log part name must be a valid identifier")

        self.dictCustomLogPart[name] = str(text)
        self._refresh_loggers_format()

    def remove_custom_log_part(self, name: str):
        """
        Remove a custom log part by name.

        If the name is not found, no action is taken.

        The name cannot be one of the reserved keywords(["timestamp", "level", "message", "userName", "machineName", "processName", "fileName", "lineNo", "projectName", "logId"]) due to they are used in machine_read log.

        Parameters:
            name: The name of the custom log part to remove from both the machine_read and human_read logs.
        """
        if name in _SET_BUILTIN_KEY:
            raise ValueError(
                f"The argumnent 'name'({name}) cann't be one of {_SET_BUILTIN_KEY}, it has been used in machine_read log."
            )
        if not name.isidentifier():
            raise ValueError("custom log part name must be a valid identifier")

        if name in self.dictCustomLogPart:
            del self.dictCustomLogPart[name]
            self._refresh_loggers_format()

    def _pretty_format_message(self, message: Any):
        """Format dict, list, tuple to make the log more readable."""
        if isinstance(message, (dict, list, tuple)):
            return json.dumps(message, indent=4, ensure_ascii=False, allow_nan=False)
        return message

    def verbose(self, message: Any, stackLevel: int = 4):
        """
        Write a log entry at the 'VERBOSE' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.log(VERBOSE_LEVEL_NUM, message, stacklevel=stackLevel, extra=extra)
        self.machineLogger.log(VERBOSE_LEVEL_NUM, message, stacklevel=stackLevel, extra=extra)

    def debug(self, message: Any, stackLevel: int = 4):
        """
        Write a log entry at the 'DEBUG' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.debug(message, stacklevel=stackLevel, extra=extra)
        self.machineLogger.debug(message, stacklevel=stackLevel, extra=extra)

    def info(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'INFO' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.info(message, stacklevel=stackLevel, extra=extra)
        self.machineLogger.info(message, stacklevel=stackLevel, extra=extra)

    def warning(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'WARNING' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.warning(message, stacklevel=stackLevel, extra=extra)
        self.machineLogger.warning(message, stacklevel=stackLevel, extra=extra)

    def error(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'ERROR' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.error(message, stacklevel=stackLevel, extra=extra)
        self.machineLogger.error(message, stacklevel=stackLevel, extra=extra)

    def critical(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'CRITICAL' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.critical(message, stacklevel=stackLevel, extra=extra)
        self.machineLogger.critical(message, stacklevel=stackLevel, extra=extra)

    def verbose_pretty(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'VERBOSE' level, only if the current log level allows it.

        If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.log(
            VERBOSE_LEVEL_NUM, self._pretty_format_message(message), stacklevel=stackLevel, extra=extra
        )
        self.machineLogger.log(VERBOSE_LEVEL_NUM, message, stacklevel=stackLevel, extra=extra)

    def debug_pretty(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'DEBUG' level, only if the current log level allows it.

        If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.debug(self._pretty_format_message(message), stacklevel=stackLevel, extra=extra)
        self.machineLogger.debug(message, stacklevel=stackLevel, extra=extra)

    def info_pretty(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'INFO' level, only if the current log level allows it.

        If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.info(self._pretty_format_message(message), stacklevel=stackLevel, extra=extra)
        self.machineLogger.info(message, stacklevel=stackLevel, extra=extra)

    def warning_pretty(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'WARNING' level, only if the current log level allows it.

        If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.warning(self._pretty_format_message(message), stacklevel=stackLevel, extra=extra)
        self.machineLogger.warning(message, stacklevel=stackLevel, extra=extra)

    def error_pretty(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'ERROR' level, only if the current log level allows it.

        If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.error(self._pretty_format_message(message), stacklevel=stackLevel, extra=extra)
        self.machineLogger.error(message, stacklevel=stackLevel, extra=extra)

    def critical_pretty(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'CRITICAL' level, only if the current log level allows it.

        If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.critical(self._pretty_format_message(message), stacklevel=stackLevel, extra=extra)
        self.machineLogger.critical(message, stacklevel=stackLevel, extra=extra)

    def set_level(self, level: LogLevel, loggerType: Literal["both", "human", "machine"] = "both"):
        """
        Set the minimum log level for the logger.

        Parameters:
            level: The minimum level to set. Must be one of ['VERBOSE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
            loggerType: Which logger to set the level for. Must be one of ['both', 'human', 'machine'].
        """
        if level not in self.dictLevel:
            raise ValueError(f"Invalid log level: {level}. Must be one of {list(self.dictLevel.keys())}.")

        if loggerType not in ["both", "human", "machine"]:
            raise ValueError(f"Invalid loggerType: {loggerType}. Must be one of ['both', 'human', 'machine'].")

        newLevel = self.dictLevel[level]

        if loggerType in ["both", "human"]:
            self.humanLogger.setLevel(newLevel)

        if loggerType in ["both", "machine"]:
            self.machineLogger.setLevel(newLevel)
        self.info(f"Set the log level to '{level}'")

    def _trace_call(
        self,
        level: LogLevel = "DEBUG",
        prefix: Literal["START", "END"] = "START",
        funcName: str = "",
    ) -> None:
        message = f"{prefix:<5}: {funcName}"
        match level:
            case "VERBOSE":
                self.verbose(message)
            case "DEBUG":
                self.debug(message)
            case "INFO":
                self.info(message)
            case "WARNING":
                self.warning(message)
            case "ERROR":
                self.error(message)
            case "CRITICAL":
                self.critical(message)
            case _:
                raise ValueError(
                    f'The argument level({level}) should be one of ["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]'
                )

    def trace(self, level: LogLevel = "DEBUG"):
        """
        This decorator logs the start and end of a function at a specified log level, default is 'DEBUG'

        Parameters:
            level: The level to record log. Must be one of ['VERBOSE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        """

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                boolError = False
                try:
                    self._trace_call(level=level, prefix="START", funcName=func.__name__)
                    return func(*args, **kwargs)
                except Exception as e:
                    self.exception_info(e)
                    boolError = True
                    raise
                finally:
                    # Log END only if no error occurred
                    if not boolError:
                        self._trace_call(level=level, prefix="END", funcName=func.__name__)

            return wrapper

        return decorator

    def exception_info(self, exObj: Exception) -> None:
        """
        Record the Exception object's 'type', 'message', 'fileName' and 'lineNumber' in a dict format and "ERROR" log level, only if the current log level allows it.

        Parameters:
            exObj: The Exception object to record.
        """
        self.error_pretty(get_exception_info(exObj))


# Log is a variable but I hope user treat it as a module, so use UpperCamelCase to match other LiberRPA modules' convention.
Log = Logger()

try:
    from liberrpa.FlowControl.ProjectFlowInit import dictFlowFile

    if dictFlowFile["logLevel"]:
        Log.set_level(level=dictFlowFile["logLevel"], loggerType="both")
    else:
        Log.set_level(level="DEBUG", loggerType="both")
except Exception:
    Log.debug(f"Failure to use '{PATH_PROJECT_FLOW}' to set log level. It is not a normal LiberRPA project?")
    Log.set_level(level="DEBUG", loggerType="both")

boolIsAdmin = ctypes.windll.shell32.IsUserAnAdmin() != 0
Log.info(f"Running as Admin: {boolIsAdmin}")


if __name__ == "__main__":
    Log.set_level("VERBOSE", loggerType="both")

    Log.verbose("verbose")
    Log.verbose_pretty(["verbose1", 1, 2, 3])

    Log.set_level("DEBUG", loggerType="both")

    Log.verbose("verbose")
    Log.verbose_pretty(["verbose2", 1, 2, 3])

    Log.add_custom_log_part(name="new", text="test")
    Log.debug("debug")
    Log.debug_pretty(["debug", 1, 2, 3])

    Log.info("info")
    Log.info_pretty({"enabled": True, "value": None, "count": 123})

    Log.warning("warning")
    Log.error("error")
    Log.critical("critical")

    @Log.trace()
    def test() -> None:
        # log.func_start()
        print("test")
        # raise ValueError("test error.")
        # log.func_end()

    test()
    Log.remove_custom_log_part("new")

    Log.info('He said "hello"')
    Log.info("Test \n test \t \\")

    # Log.remove_custom_log_part(name="new")
    test()
    # Log.debug_pretty((1,2,3))

    # try:
    #     raise ValueError("test error.")

    # except Exception as e:
    #     log.exception_info(e)
