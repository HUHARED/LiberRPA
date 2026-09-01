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
    STR_PROJECT_ROOT,
    PATH_PROJECT_FLOW,
    PROCESS_NAME,
)
from liberrpa.Common._BasicConfig import (
    BasicConfigToolName,
    get_basic_config_dict,
    get_liberrpa_folder_path,
)
from liberrpa.Common._RunContext import (
    get_executor_run_context,
    get_or_create_run_started_at,
    write_executor_run_state,
)
from liberrpa.Common._Exception import get_exception_info
from liberrpa.Common._LogFormatter import create_human_read_formatter

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
from collections.abc import Callable
from typing import Any, Literal, cast, TypeVar

VERBOSE_LEVEL_NUM = 5
logging.addLevelName(VERBOSE_LEVEL_NUM, "VERBOSE")
type LogLevel = Literal["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Public Log.xxx() methods call a shared helper before entering Python logging internals.
# With the current call chain, this stacklevel points log records back to the user call site.
_INT_PUBLIC_LOG_STACKLEVEL = 5


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

F = TypeVar("F", bound=Callable[..., Any])


def _find_caller(
    stack_info: bool = False, stacklevel: int = 2
) -> tuple[str, int, str, str | None]:
    """
    Find the stack frame of the caller so that we can note the source file name, line number, and function name.
    """
    f = logging.currentframe()
    if f is not None:
        for _ in range(stacklevel):
            if f is None:
                break
            f = f.f_back
    rv = "(unknown file)", 0, "(unknown function)", None
    if f is not None:
        co = f.f_code
        sinfo = None
        if stack_info:
            sio = io.StringIO()
            sio.write("Stack (most recent call last):\n")
            traceback.print_stack(f, file=sio)
            sinfo = sio.getvalue()
            if sinfo[-1] == "\n":
                sinfo = sinfo[:-1]
            sio.close()
        rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
    return rv


class JsonLineFormatter(logging.Formatter):
    def __init__(self, projectName: str, customLogPartDict: dict[str, str]) -> None:
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
            self._wrap_by_bracket_and_generate_color(
                strTimestamp, self.FIELD_STYLES["timestamp"]
            ),
            self._wrap_by_bracket_and_generate_color(
                strLevel, self.LEVEL_STYLES.get(strLevel, "")
            ),
        ]

        if record.processName != "MainProcess":
            listParts.append(
                self._wrap_by_bracket_and_generate_color(
                    record.processName, self.FIELD_STYLES["processName"]
                )
            )

        if record.filename not in _SET_INTERNAL_FILE:
            listParts.append(
                self._wrap_by_bracket_and_generate_color(
                    record.filename, self.FIELD_STYLES["fileName"]
                )
            )
            listParts.append(
                self._wrap_by_bracket_and_generate_color(
                    record.lineno, self.FIELD_STYLES["lineNo"]
                )
            )

        for name in self.listCustomLogPart:
            value = getattr(record, name, "")
            listParts.append(
                self._wrap_by_bracket_and_generate_color(
                    value, self.FIELD_STYLES["custom"]
                )
            )

        message = record.getMessage()
        if message.startswith(("CALL  :", "RETURN:", "FLOW  :", "EVAL  :")):
            message = self._highlight_trace(message)
        else:
            message = self._highlight_message_tokens(message)

        result = "".join(listParts) + " " + message

        return result


class Logger:
    def __init__(self) -> None:

        self.dictCustomLogPart: dict[str, str] = {}
        self.dictLevel = {
            "VERBOSE": VERBOSE_LEVEL_NUM,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        strToolName: BasicConfigToolName
        strLogFolderName = os.getenv("LogFolderName")
        dictExecutorRunContext = (
            None if strLogFolderName is not None else get_executor_run_context()
        )
        datetimeStartedAt = get_or_create_run_started_at()
        strStartedAtFolderName = datetimeStartedAt.strftime("%Y-%m-%d_%H%M%S")

        if strLogFolderName is not None:
            strToolName = "BuiltInTools"
            self.strProjectName = strLogFolderName
            # Built-in tools may run repeatedly within the same second and do not have an Executor run ID.
            strStartedAtFolderName = datetimeStartedAt.strftime("%Y-%m-%d_%H%M%S_%f")
            print("Set log folder name:", strLogFolderName)

        elif dictExecutorRunContext is not None:
            strToolName = "Executor"
            self.strProjectName = dictExecutorRunContext.packageName

        else:
            strToolName = "Editor"
            self.strProjectName = os.path.basename(STR_PROJECT_ROOT)

        self.dictBasicConfig = get_basic_config_dict(toolName=strToolName)

        if dictExecutorRunContext is not None and strLogFolderName is None:
            # Run by Executor.
            try:
                dictExecutorConfig = cast(
                    dict[str, str],
                    json5.loads(
                        Path(
                            os.path.join(
                                get_liberrpa_folder_path(), "./configFiles/Executor.jsonc"
                            )
                        ).read_text(encoding="utf-8", errors="strict")
                    ),
                )

                strProjectLogFolderPath = dictExecutorConfig.get(
                    "projectLogFolderPath", ""
                )
                strLogBasePath = (
                    strProjectLogFolderPath or self.dictBasicConfig["outputLogPath"]
                )
                strShortRunId = dictExecutorRunContext.runId.split("-", maxsplit=1)[0]
                strRunFolderName = f"{strStartedAtFolderName}_{strShortRunId}"

                self.strLogFolder = sanitize_filepath(
                    os.path.join(
                        strLogBasePath,
                        self.strProjectName,
                        dictExecutorRunContext.packageVersion,
                        strRunFolderName,
                    )
                )

            except Exception as e:
                raise Exception(f"Error in handle Executor file: {e}")
        else:
            # Run by Editor.
            self.strLogFolder = sanitize_filepath(
                os.path.join(
                    self.dictBasicConfig["outputLogPath"],
                    self.strProjectName,
                    strStartedAtFolderName,
                )
            )

        # All processes create the folder to avoid a subprocess writing a file before MainProcess.
        os.makedirs(self.strLogFolder, exist_ok=True)

        # Only the MainProcess publishes Executor runtime state.
        if PROCESS_NAME == "MainProcess" and dictExecutorRunContext is not None:
            write_executor_run_state(status="running", logPath=self.strLogFolder)

        # Executor runs keep formal logs in files. Console output is reserved for Editor and built-in tool runs.
        self.colorfulConsoleHandlerObj = (
            None
            if dictExecutorRunContext is not None
            else logging.StreamHandler(stream=sys.stderr)
        )  # Console handler
        self.humanLogger = self._create_logger(
            f"human_read_{PROCESS_NAME}.log", humanReadable=True
        )
        if self.colorfulConsoleHandlerObj is not None:
            self.humanLogger.addHandler(
                self.colorfulConsoleHandlerObj
            )  # Add the StreamHandler to human_logger
        self.machineLogger = self._create_logger(
            fileName=f"machine_read_{PROCESS_NAME}.jsonl", humanReadable=False
        )

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
        fileHandlerObj = RotatingFileHandler(
            strLogFilePath, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )

        if humanReadable:
            formatter = self._get_human_formatter()
            if self.colorfulConsoleHandlerObj is not None:
                self.colorfulConsoleHandlerObj.setFormatter(self._get_console_formatter())
        else:
            formatter = self._get_json_formatter()

        fileHandlerObj.setFormatter(formatter)
        logger.addHandler(fileHandlerObj)

        logger.findCaller = _find_caller
        return logger

    def _get_human_formatter(self) -> logging.Formatter:
        return create_human_read_formatter(
            includeProcessName=PROCESS_NAME != "MainProcess",
            sourceHiddenFileNameSet=_SET_INTERNAL_FILE,
            customLogPart=self.dictCustomLogPart,
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
        if self.colorfulConsoleHandlerObj is not None:
            self.colorfulConsoleHandlerObj.setFormatter(self._get_console_formatter())
        self.machineLogger.handlers[0].setFormatter(self._get_json_formatter())

    def add_custom_log_part(self, name: str, text: str) -> None:
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
                f"The argument 'name'({name}) cannot be one of {_SET_BUILTIN_KEY}, it has been used in machine_read log."
            )
        if not name.isidentifier():
            raise ValueError("custom log part name must be a valid identifier")

        self.dictCustomLogPart[name] = str(text)
        self._refresh_loggers_format()

    def remove_custom_log_part(self, name: str) -> None:
        """
        Remove a custom log part by name.

        If the name is not found, no action is taken.

        The name cannot be one of the reserved keywords(["timestamp", "level", "message", "userName", "machineName", "processName", "fileName", "lineNo", "projectName", "logId"]) due to they are used in machine_read log.

        Parameters:
            name: The name of the custom log part to remove from both the machine_read and human_read logs.
        """
        if name in _SET_BUILTIN_KEY:
            raise ValueError(
                f"The argument 'name'({name}) cannot be one of {_SET_BUILTIN_KEY}, it has been used in machine_read log."
            )
        if not name.isidentifier():
            raise ValueError("custom log part name must be a valid identifier")

        if name in self.dictCustomLogPart:
            del self.dictCustomLogPart[name]
            self._refresh_loggers_format()

    def _format(self, message: Any) -> str:
        """
        Format a single value for the human_read log only.

        This improves readability for dict, list, and tuple values in human-readable logs.
        The machine_read log keeps the original value unchanged.
        """
        if isinstance(message, (dict, list, tuple)):
            try:
                return json.dumps(message, indent=4, ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError):
                return repr(message)

        return str(message)

    def _build_human_message(
        self, messages: tuple[Any, ...], sep: str, formatMessage: bool
    ) -> str:
        if not messages:
            return ""

        if formatMessage:
            return sep.join(self._format(message) for message in messages)

        return sep.join(str(message) for message in messages)

    def _build_machine_message(self, messages: tuple[Any, ...]) -> Any:
        if not messages:
            return ""

        if len(messages) == 1:
            return messages[0]

        return list(messages)

    def _write_log(
        self, level: int, messages: tuple[Any, ...], sep: str, formatMessage: bool
    ) -> None:
        extra = self._get_custom_log_parts()
        humanMessage = self._build_human_message(
            messages=messages, sep=sep, formatMessage=formatMessage
        )
        machineMessage = self._build_machine_message(messages=messages)

        self.humanLogger.log(
            level, humanMessage, stacklevel=_INT_PUBLIC_LOG_STACKLEVEL, extra=extra
        )
        self.machineLogger.log(
            level, machineMessage, stacklevel=_INT_PUBLIC_LOG_STACKLEVEL, extra=extra
        )

    def verbose(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a log entry at the VERBOSE level, only if the current log level allows it.

        Parameters:
            messages: Values to write to the log. Multiple values are converted to strings and joined by sep in the human_read log. In the machine_read log, a single value is stored as-is, and multiple values are stored as a list of original values.
            sep: Separator inserted between multiple values in the human_read log. It does not change values stored in the machine_read log.
        """
        self._write_log(
            level=VERBOSE_LEVEL_NUM, messages=messages, sep=sep, formatMessage=False
        )

    def debug(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a log entry at the DEBUG level, only if the current log level allows it.

        Parameters:
            messages: Values to write to the log. Multiple values are converted to strings and joined by sep in the human_read log. In the machine_read log, a single value is stored as-is, and multiple values are stored as a list of original values.
            sep: Separator inserted between multiple values in the human_read log. It does not change values stored in the machine_read log.
        """
        self._write_log(
            level=logging.DEBUG, messages=messages, sep=sep, formatMessage=False
        )

    def info(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a log entry at the INFO level, only if the current log level allows it.

        Parameters:
            messages: Values to write to the log. Multiple values are converted to strings and joined by sep in the human_read log. In the machine_read log, a single value is stored as-is, and multiple values are stored as a list of original values.
            sep: Separator inserted between multiple values in the human_read log. It does not change values stored in the machine_read log.
        """
        self._write_log(
            level=logging.INFO, messages=messages, sep=sep, formatMessage=False
        )

    def warning(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a log entry at the WARNING level, only if the current log level allows it.

        Parameters:
            messages: Values to write to the log. Multiple values are converted to strings and joined by sep in the human_read log. In the machine_read log, a single value is stored as-is, and multiple values are stored as a list of original values.
            sep: Separator inserted between multiple values in the human_read log. It does not change values stored in the machine_read log.
        """
        self._write_log(
            level=logging.WARNING, messages=messages, sep=sep, formatMessage=False
        )

    def error(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a log entry at the ERROR level, only if the current log level allows it.

        Parameters:
            messages: Values to write to the log. Multiple values are converted to strings and joined by sep in the human_read log. In the machine_read log, a single value is stored as-is, and multiple values are stored as a list of original values.
            sep: Separator inserted between multiple values in the human_read log. It does not change values stored in the machine_read log.
        """
        self._write_log(
            level=logging.ERROR, messages=messages, sep=sep, formatMessage=False
        )

    def critical(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a log entry at the CRITICAL level, only if the current log level allows it.

        Parameters:
            messages: Values to write to the log. Multiple values are converted to strings and joined by sep in the human_read log. In the machine_read log, a single value is stored as-is, and multiple values are stored as a list of original values.
            sep: Separator inserted between multiple values in the human_read log. It does not change values stored in the machine_read log.
        """
        self._write_log(
            level=logging.CRITICAL, messages=messages, sep=sep, formatMessage=False
        )

    def verbose_pretty(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a formatted log entry at the VERBOSE level, only if the current log level allows it.

        Dict, list, and tuple values are formatted with indentation in the human_read log only. The machine_read log keeps the original values unchanged.

        Parameters:
            messages: Values to write to the log.
            sep: Separator inserted between multiple values in the human_read log.
        """
        self._write_log(
            level=VERBOSE_LEVEL_NUM, messages=messages, sep=sep, formatMessage=True
        )

    def debug_pretty(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a formatted log entry at the DEBUG level, only if the current log level allows it.

        Dict, list, and tuple values are formatted with indentation in the human_read log only. The machine_read log keeps the original values unchanged.

        Parameters:
            messages: Values to write to the log.
            sep: Separator inserted between multiple values in the human_read log.
        """
        self._write_log(
            level=logging.DEBUG, messages=messages, sep=sep, formatMessage=True
        )

    def info_pretty(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a formatted log entry at the INFO level, only if the current log level allows it.

        Dict, list, and tuple values are formatted with indentation in the human_read log only. The machine_read log keeps the original values unchanged.

        Parameters:
            messages: Values to write to the log.
            sep: Separator inserted between multiple values in the human_read log.
        """
        self._write_log(
            level=logging.INFO, messages=messages, sep=sep, formatMessage=True
        )

    def warning_pretty(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a formatted log entry at the WARNING level, only if the current log level allows it.

        Dict, list, and tuple values are formatted with indentation in the human_read log only. The machine_read log keeps the original values unchanged.

        Parameters:
            messages: Values to write to the log.
            sep: Separator inserted between multiple values in the human_read log.
        """
        self._write_log(
            level=logging.WARNING, messages=messages, sep=sep, formatMessage=True
        )

    def error_pretty(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a formatted log entry at the ERROR level, only if the current log level allows it.

        Dict, list, and tuple values are formatted with indentation in the human_read log only. The machine_read log keeps the original values unchanged.

        Parameters:
            messages: Values to write to the log.
            sep: Separator inserted between multiple values in the human_read log.
        """
        self._write_log(
            level=logging.ERROR, messages=messages, sep=sep, formatMessage=True
        )

    def critical_pretty(self, *messages: Any, sep: str = " ") -> None:
        """
        Write a formatted log entry at the CRITICAL level, only if the current log level allows it.

        Dict, list, and tuple values are formatted with indentation in the human_read log only. The machine_read log keeps the original values unchanged.

        Parameters:
            messages: Values to write to the log.
            sep: Separator inserted between multiple values in the human_read log.
        """
        self._write_log(
            level=logging.CRITICAL, messages=messages, sep=sep, formatMessage=True
        )

    def set_level(
        self, level: LogLevel, loggerType: Literal["both", "human", "machine"] = "both"
    ) -> None:
        """
        Set the minimum log level for the logger.

        Parameters:
            level: The minimum level to set. Must be one of ['VERBOSE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
            loggerType: Which logger to set the level for. Must be one of ['both', 'human', 'machine'].
        """
        if level not in self.dictLevel:
            raise ValueError(
                f"Invalid log level: {level}. Must be one of {list(self.dictLevel.keys())}."
            )

        if loggerType not in ["both", "human", "machine"]:
            raise ValueError(
                f"Invalid loggerType: {loggerType}. Must be one of ['both', 'human', 'machine']."
            )

        newLevel = self.dictLevel[level]

        if loggerType in ["both", "human"]:
            self.humanLogger.setLevel(newLevel)

        if loggerType in ["both", "machine"]:
            self.machineLogger.setLevel(newLevel)
        self.info(f"Set the log level to '{level}'")

    def _trace_call(
        self,
        level: LogLevel = "DEBUG",
        prefix: Literal["CALL", "RETURN"] = "CALL",
        funcName: str = "",
    ) -> None:
        message = f"{prefix:<6}: {funcName}"
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

    def trace(self, level: LogLevel = "DEBUG") -> Callable[[F], F]:
        """
        Decorate a function to log its call and successful return at a specified log level.

        Parameters:
            level: The level to record log. Must be one of ['VERBOSE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].

        Returns:
            Callable[[F], F]: A decorator that preserves the target function's type.
        """

        def decorator(func: F) -> F:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                boolError = False
                try:
                    self._trace_call(level=level, prefix="CALL", funcName=func.__name__)
                    return func(*args, **kwargs)
                except Exception:
                    # self.exception_info(e)
                    boolError = True
                    raise
                finally:
                    # Log RETURN only if the function completed without raising an exception.
                    if not boolError:
                        self._trace_call(
                            level=level, prefix="RETURN", funcName=func.__name__
                        )

            return cast(F, wrapper)

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

if PATH_PROJECT_FLOW.is_file():
    # Flow Project
    try:
        from liberrpa.FlowControl.ProjectFlowInit import dictFlowFile

        if dictFlowFile["logLevel"]:
            Log.set_level(level=dictFlowFile["logLevel"], loggerType="both")
        else:
            Log.set_level(level="DEBUG", loggerType="both")
    except Exception as e:
        Log.warning(
            f"Could not load the log level from '{PATH_PROJECT_FLOW}': {e}. Using the default log level 'DEBUG'."
        )
        Log.set_level(level="DEBUG", loggerType="both")
else:
    Log.debug(
        f"No project.flow was found at '{PATH_PROJECT_FLOW}'. Using the default log level 'DEBUG'."
    )
    Log.set_level(level="DEBUG", loggerType="both")

boolIsAdmin = ctypes.windll.shell32.IsUserAnAdmin() != 0
Log.debug(f"Running as Admin: {boolIsAdmin}")


if __name__ == "__main__":
    pass
