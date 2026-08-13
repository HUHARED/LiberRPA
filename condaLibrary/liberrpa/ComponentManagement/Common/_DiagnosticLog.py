# FileName: _DiagnosticLog.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._BasicConfig import get_basic_config_dict
from liberrpa.Common._LogFormatter import create_human_read_formatter

from datetime import datetime
import json
import logging
import os
from pathlib import Path
from types import TracebackType
from typing import Literal, cast


type ComponentManagementDiagnosticLogLevel = Literal[
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]

_STR_LOG_LEVEL_ENV_NAME = "LIBERRPA_COMPONENT_MANAGEMENT_LOG_LEVEL"
_STR_DEFAULT_LOG_LEVEL: ComponentManagementDiagnosticLogLevel = "DEBUG"
_DICT_LOG_LEVEL: dict[ComponentManagementDiagnosticLogLevel, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class _SilentFileHandler(logging.FileHandler):
    def handleError(self, _record: logging.LogRecord) -> None:
        # Diagnostic logging must never write handler failures to stderr because stderr is reserved for fatal Component Management process failures.
        return None


class ComponentManagementDiagnosticLogger:
    def __init__(self) -> None:
        self._loggerObj: logging.Logger | None = None
        self._logFilePath: Path | None = None

    @property
    def logFilePath(self) -> Path | None:
        return self._logFilePath

    @property
    def initialized(self) -> bool:
        return self._loggerObj is not None

    def initialize(self) -> Path:
        if self._loggerObj is not None and self._logFilePath is not None:
            return self._logFilePath

        strConfiguredLevel = (
            os
            .getenv(
                _STR_LOG_LEVEL_ENV_NAME,
                _STR_DEFAULT_LOG_LEVEL,
            )
            .strip()
            .upper()
        )
        boolInvalidLogLevel = strConfiguredLevel not in _DICT_LOG_LEVEL
        if boolInvalidLogLevel:
            strLogLevel = _STR_DEFAULT_LOG_LEVEL
        else:
            strLogLevel = cast(
                ComponentManagementDiagnosticLogLevel,
                strConfiguredLevel,
            )

        dictBasicConfig = get_basic_config_dict(toolName="BuiltInTools")
        pathLogFolder = Path(dictBasicConfig["outputLogPath"]) / "_ComponentManagement"
        pathLogFolder.mkdir(parents=True, exist_ok=True)

        datetimeNow = datetime.now()
        pathLogFile = pathLogFolder / (
            "component_management_"
            f"{datetimeNow.strftime('%Y-%m-%d_%H%M%S_%f')}_"
            f"{os.getpid()}.log"
        )

        loggerObj = logging.getLogger(
            f"liberrpa.ComponentManagement.{os.getpid()}.{id(self)}"
        )
        for handlerObj in loggerObj.handlers[:]:
            loggerObj.removeHandler(handlerObj)
            handlerObj.close()

        loggerObj.handlers.clear()
        loggerObj.propagate = False
        loggerObj.setLevel(_DICT_LOG_LEVEL[strLogLevel])

        fileHandlerObj = _SilentFileHandler(
            pathLogFile,
            mode="x",
            encoding="utf-8",
        )
        fileHandlerObj.setLevel(_DICT_LOG_LEVEL[strLogLevel])
        fileHandlerObj.setFormatter(
            create_human_read_formatter(
                includeProcessName=False,
            )
        )
        loggerObj.addHandler(fileHandlerObj)

        self._loggerObj = loggerObj
        self._logFilePath = pathLogFile

        if boolInvalidLogLevel:
            self.warning(
                f"Invalid {_STR_LOG_LEVEL_ENV_NAME} value {strConfiguredLevel!r}; using {_STR_DEFAULT_LOG_LEVEL}."
            )

        self.debug(f"Diagnostic log initialized: {pathLogFile}")
        return pathLogFile

    def close(self) -> None:
        loggerObj = self._loggerObj
        if loggerObj is None:
            return

        for handlerObj in loggerObj.handlers[:]:
            try:
                handlerObj.flush()
                handlerObj.close()
            except Exception:
                pass
            finally:
                loggerObj.removeHandler(handlerObj)

        loggerObj.handlers.clear()
        self._loggerObj = None

    def _format_message(self, message: object) -> str:
        if isinstance(message, (dict, list, tuple)):
            try:
                return json.dumps(
                    message,
                    indent=4,
                    ensure_ascii=False,
                    allow_nan=False,
                    default=repr,
                )
            except (TypeError, ValueError):
                return repr(message)

        return str(message)

    def _log(
        self,
        level: int,
        message: object,
        *,
        stackLevel: int,
        excInfo: (
            tuple[type[BaseException], BaseException, TracebackType | None] | None
        ) = None,
    ) -> None:
        loggerObj = self._loggerObj
        if loggerObj is None:
            return

        try:
            loggerObj.log(
                level,
                self._format_message(message),
                stacklevel=stackLevel,
                exc_info=excInfo,
            )
        except Exception:
            # Diagnostic logging must not change the Component operation result.
            return

    def debug(self, message: object, stackLevel: int = 3) -> None:
        self._log(logging.DEBUG, message, stackLevel=stackLevel)

    def info(self, message: object, stackLevel: int = 3) -> None:
        self._log(logging.INFO, message, stackLevel=stackLevel)

    def warning(self, message: object, stackLevel: int = 3) -> None:
        self._log(logging.WARNING, message, stackLevel=stackLevel)

    def error(self, message: object, stackLevel: int = 3) -> None:
        self._log(logging.ERROR, message, stackLevel=stackLevel)

    def critical(self, message: object, stackLevel: int = 3) -> None:
        self._log(logging.CRITICAL, message, stackLevel=stackLevel)

    def debug_exception(
        self,
        message: object,
        errorObj: BaseException,
        stackLevel: int = 3,
    ) -> None:
        self._log(
            logging.DEBUG,
            message,
            stackLevel=stackLevel,
            excInfo=(type(errorObj), errorObj, errorObj.__traceback__),
        )

    def exception(
        self,
        message: object,
        errorObj: BaseException,
        stackLevel: int = 3,
    ) -> None:
        self._log(
            logging.ERROR,
            message,
            stackLevel=stackLevel,
            excInfo=(type(errorObj), errorObj, errorObj.__traceback__),
        )


# Keep the module-style naming convention used by liberrpa.Logging.Log.
DiagnosticLog = ComponentManagementDiagnosticLogger()
