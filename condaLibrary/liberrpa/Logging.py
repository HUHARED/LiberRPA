# FileName: Logging.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import liberrpa.Common._Initialization  # For initialization

import multiprocessing
from liberrpa.Common._BasicConfig import get_basic_config_dict, get_liberrpa_folder_path
from liberrpa.Common._Exception import get_exception_info

import os
from pathlib import Path
from uuid import uuid4
import json
import socket
from logging.handlers import RotatingFileHandler
import logging
import multiprocessing
import sys
from functools import wraps
import ctypes
from pathvalidate import sanitize_filepath
from typing import Any, Literal


VERBOSE_LEVEL_NUM = 5

logging.addLevelName(VERBOSE_LEVEL_NUM, "VERBOSE")


type LogLevel = Literal["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

processName = multiprocessing.current_process().name

listBuildinWord = [
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
]


def _find_caller(stack_info=False, stacklevel=2):
    """
    Find the stack frame of the caller so that we can note the source file name, line number, and function name.
    """
    f = logging.currentframe()
    if f is not None:
        for _ in range(stacklevel):
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
    def __init__(self, fmt: str, datefmt: str):
        super().__init__(fmt, datefmt)
        self.original_fmt = fmt

    def format(self, record) -> str:
        if record.filename in [
            "Logging.py",
            "Run.py",
            "End.py",
            "ProjectFlowInit.py",
            "_UiElement.py",
            "_WebSocket.py",
            "Trigger.py",
        ]:
            # Not record [%(filename)s][%(lineno)d] in human-read log if the finename is "Logging.py", to make the log more concise.
            fmtNew = self.original_fmt.replace("[%(filename)s][%(lineno)d]", "")
            self._style._fmt = fmtNew
            formatted = super().format(record)
            self._style._fmt = self.original_fmt
            return formatted
        else:
            return super().format(record)


class Logger:
    def __init__(self) -> None:
        self.dictEditorConfig = get_basic_config_dict()
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

        dictProject: dict[str, Any] = json.loads(Path("project.json").read_text(encoding="utf-8"))

        strLogFolderName = os.getenv("LogFolderName")
        if strLogFolderName is not None:
            self.strProjectName = strLogFolderName
            print("Set log folder name:", strLogFolderName)

        elif dictProject.get("executorPackage") == True:
            # Executor package's name is not the project name, use data in project.json
            self.strProjectName = dictProject["executorPackageName"]

        else:
            self.strProjectName = os.path.basename(os.getcwd())

        # If it's an Executor package, add version subfolder.
        if dictProject.get("executorPackage") == True:
            try:

                dictExecutorConfig: dict[str, str] = json.loads(
                    Path(os.path.join(get_liberrpa_folder_path(), "./configFiles/Executor.jsonc")).read_text()
                )

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
                            self.dictEditorConfig["outputLogPath"],
                            self.strProjectName,
                            dictProject["executorPackageVersion"],
                            dictProject["lastStartUpTime"],
                        )
                    )
            except Exception as e:
                print(f"Error in handle executor file: {e}")
        else:
            self.strLogFolder = sanitize_filepath(
                os.path.join(
                    self.dictEditorConfig["outputLogPath"],
                    self.strProjectName,
                    dictProject["lastStartUpTime"],
                )
            )

        # Update project.json, add "logPath" for other parts to use later. Such as screen recording, screenshot.
        # Only the MainProcess can initialize log folder.
        if processName == "MainProcess":
            dictProject["logPath"] = self.strLogFolder
            dictProject["executorPackageStatus"] = "running"
            strTemp = json.dumps(dictProject, indent=4, ensure_ascii=False)
            Path("project.json").write_text(data=strTemp, encoding="utf-8", errors="strict")
            print("Update project.json: " + strTemp)

            os.makedirs(self.strLogFolder, exist_ok=True)

        # Create loggers
        self.consoleHandlerObj = logging.StreamHandler(stream=sys.stderr)  # Console handler
        self.humanLogger = self._create_logger(f"human_read_{processName}.log", humanReadable=True)
        self.humanLogger.addHandler(self.consoleHandlerObj)  # Add the StreamHandler to human_logger
        self.machineLogger = self._create_logger(fileName=f"machine_read_{processName}.jsonl", humanReadable=False)

    def _create_logger(self, fileName: str, humanReadable: bool) -> logging.Logger:
        logger = logging.getLogger(fileName)
        logger.setLevel(logging.DEBUG)
        strLogFilePath = os.path.join(self.strLogFolder, fileName)
        fileHandlerObj = RotatingFileHandler(strLogFilePath, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")

        if humanReadable:
            formatter = self._get_human_formatter()
            self.consoleHandlerObj.setFormatter(formatter)
        else:
            formatter = self._get_json_formatter()

        fileHandlerObj.setFormatter(formatter)
        logger.addHandler(fileHandlerObj)

        logger.findCaller = _find_caller
        return logger

    def _get_human_formatter(self) -> logging.Formatter:
        # Not show processName in MainProcess to make log more concise.
        if processName != "MainProcess":
            strFormat = "[%(asctime)s][%(levelname)s][%(processName)s][%(filename)s][%(lineno)d]"
        else:
            strFormat = "[%(asctime)s][%(levelname)s][%(filename)s][%(lineno)d]"
        for key in self.dictCustomLogPart:
            strFormat += "[%(" + key + ")s]"
        strFormat += " %(message)s"
        return ConditionalHumanReadFormatter(strFormat, datefmt="%Y-%m-%d %H:%M:%S")

    def _get_json_formatter(self) -> logging.Formatter:
        dictJson = {
            "timestamp": "%(asctime)s",
            "level": "%(levelname)s",
            "message": "%(message)s",
            "userName": os.getlogin(),
            "machineName": socket.gethostname(),
            "processName": "%(processName)s",
            "fileName": "%(filename)s",
            "lineNo": "%(lineno)d",
            "projectName": self.strProjectName,
            "logId": str(uuid4()),
        }
        dictJson.update(self.dictCustomLogPart)
        return logging.Formatter(json.dumps(dictJson))

    def _get_custom_log_parts(self):
        # Evaluate custom log parts and return them
        parts = {}
        for key, value in self.dictCustomLogPart.items():
            """if callable(value):
                parts[key] = value()
            else:
                parts[key] = value"""
            parts[key] = value
        return parts

    def _refresh_loggers_format(self):
        # Refresh format for both loggers

        self.humanLogger.handlers[0].setFormatter(self._get_human_formatter())
        self.consoleHandlerObj.setFormatter(self._get_human_formatter())
        self.machineLogger.handlers[0].setFormatter(self._get_json_formatter())

        if len(self.humanLogger.handlers) > 1 and isinstance(self.humanLogger.handlers[1], logging.StreamHandler):
            self.humanLogger.handlers[1].setFormatter(self._get_human_formatter())

    def add_custom_log_part(self, name: str, text: str):
        """
        Adds a new part to the log entry format.

        If the name already exists, the text will be updated.

        The name cannot be one of the reserved keywords(["timestamp", "level", "message", "userName", "machineName", "processName", "fileName", "lineNo", "projectName", "logId"]) due to they are used in machine_read log.

        Parameters:
            name: The new part's name to be added. This will be a new key in the machine_read log entry, but it won't appear in human_read log.
            text: The text of the new log part, which will be displayed in human_read log.
        """

        if name in listBuildinWord:
            raise ValueError(
                f"The argumnent 'name'({name}) cann't be one of {listBuildinWord}, it has been used in machine_read log."
            )
        self.dictCustomLogPart[name] = text
        self._refresh_loggers_format()

    def remove_custom_log_part(self, name: str):
        """
        Remove a custom log part by name.

        If the name is not found, no action is taken.

        The name cannot be one of the reserved keywords(["timestamp", "level", "message", "userName", "machineName", "processName", "fileName", "lineNo", "projectName", "logId"]) due to they are used in machine_read log.

        Parameters:
            name: The name of the custom log part to remove from both the machine_read and human_read logs.
        """
        if name in listBuildinWord:
            raise ValueError(
                f"The argumnent 'name'({name}) cann't be one of {listBuildinWord}, it has been used in machine_read log."
            )
        if name in self.dictCustomLogPart:
            del self.dictCustomLogPart[name]
            self._refresh_loggers_format()

    def _pretty_format_message(self, message: Any):
        """Format dict, list, tuple to make the log more readable."""
        if isinstance(message, (dict, list, tuple)):
            return json.dumps(message, indent=4, ensure_ascii=False)
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
        try:
            self.machineLogger.log(VERBOSE_LEVEL_NUM, repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.log(
                VERBOSE_LEVEL_NUM, str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra
            )

    def debug(self, message: Any, stackLevel: int = 4):
        """
        Write a log entry at the 'DEBUG' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.debug(message, stacklevel=stackLevel, extra=extra)
        try:
            self.machineLogger.debug(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.debug(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

    def info(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'INFO' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.info(message, stacklevel=stackLevel, extra=extra)
        try:
            self.machineLogger.info(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.info(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

    def warning(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'WARNING' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.warning(message, stacklevel=stackLevel, extra=extra)
        try:
            self.machineLogger.warning(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.warning(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

    def error(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'ERROR' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.error(message, stacklevel=stackLevel, extra=extra)
        try:
            self.machineLogger.error(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.error(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

    def critical(self, message: Any, stackLevel=4):
        """
        Write a log entry at the 'CRITICAL' level, only if the current log level allows it.

        Parameters:
            message: The message to log, which can be any type that can be converted to a string.
            stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
        """
        extra = self._get_custom_log_parts()
        self.humanLogger.critical(message, stacklevel=stackLevel, extra=extra)
        try:
            self.machineLogger.critical(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.critical(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

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
        try:
            self.machineLogger.log(VERBOSE_LEVEL_NUM, repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.log(
                VERBOSE_LEVEL_NUM, str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra
            )

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
        try:
            self.machineLogger.debug(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.debug(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

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
        try:
            self.machineLogger.info(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.info(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

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
        try:
            self.machineLogger.warning(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.warning(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

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
        try:
            self.machineLogger.error(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.error(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

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
        try:
            self.machineLogger.critical(repr(message), stacklevel=stackLevel, extra=extra)
        except Exception as e:
            self.machineLogger.critical(str(message).replace("\n", R"\n"), stacklevel=stackLevel, extra=extra)

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
        prefix: Literal["START", "END  "] = "START",
        funcName: str = "",
    ) -> None:
        match level:
            case "VERBOSE":
                self.verbose(f"{prefix}: {funcName}")
            case "DEBUG":
                self.debug(f"{prefix}: {funcName}")
            case "INFO":
                self.info(f"{prefix}: {funcName}")
            case "WARNING":
                self.warning(f"{prefix}: {funcName}")
            case "ERROR":
                self.error(f"{prefix}: {funcName}")
            case "CRITICAL":
                self.critical(f"{prefix}: {funcName}")
            case _:
                raise ValueError(
                    f'The argument level({level}) should be one of ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]'
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
                    raise e
                finally:
                    # Log END only if no error occurred
                    if not boolError:
                        self._trace_call(level=level, prefix="END  ", funcName=func.__name__)

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
except Exception as e:
    Log.debug(f"Failure to use '{os.getcwd()+"\\project.flow"}' to set log level. It is not a normal LiberRPA project?")
    Log.set_level(level="DEBUG", loggerType="both")

boolIsAdmin = ctypes.windll.shell32.IsUserAnAdmin() != 0
Log.info(f"Running as Admin: {boolIsAdmin}")


if __name__ == "__main__":

    Log.set_level("DEBUG", loggerType="both")

    Log.verbose("verbose")
    Log.verbose_pretty(["verbose", 1, 2, 3])

    # Log.add_custom_log_part(name="new", text="test")
    Log.debug("debug")
    Log.debug_pretty(["debug", 1, 2, 3])
    Log.info("info")

    @Log.trace()
    def test() -> None:
        # log.func_start()
        print("test")
        # raise ValueError("test error.")
        # log.func_end()

    test()

    # Log.remove_custom_log_part(name="new")
    test()
    # Log.debug_pretty((1,2,3))

    # try:
    #     raise ValueError("test error.")

    # except Exception as e:
    #     log.exception_info(e)
