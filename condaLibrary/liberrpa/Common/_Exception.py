# FileName: _Exception.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import traceback
import sys
from typing import TypedDict
import multiprocessing


class UiElementNotFoundError(Exception):
    """Custom exception for UI not found"""

    def __init__(self, message="Not found the target element.", *args):
        super().__init__(message, *args)


class UiTimeoutError(Exception):
    """Custom exception for UI operation timeout"""

    def __init__(self, message="Timeout for UI operation exceeded.", *args):
        super().__init__(message, *args)


class UiOperationError(Exception):
    """Custom exception for UI operation"""

    def __init__(self, message="Have some arguments that the target element doesn't support.", *args):
        super().__init__(message, *args)


class ChromeError(Exception):
    """Custom exception for Chrome manipulation."""

    def __init__(self, message="Error when manipulating Chrome.", *args):
        super().__init__(message, *args)


class MailError(Exception):
    """Custom exception for Mail manipulation."""

    def __init__(self, message="Error when manipulating Mail.", *args):
        super().__init__(message, *args)


class QtError(Exception):
    """Custom exception for QtWorker."""

    def __init__(self, message="Error when manipulating QT object.", *args):
        super().__init__(message, *args)


class DictExceptionInfo(TypedDict):
    type: str
    message: str
    fileName: str
    lineNumber: int | None
    process: str


def get_exception_info(ex: Exception) -> DictExceptionInfo:
    excType, excObj, excTraceback = sys.exc_info()
    fileName = traceback.extract_tb(excTraceback)[-1].filename
    lineNumber = traceback.extract_tb(excTraceback)[-1].lineno
    excMessage = str(ex)
    excTypeName = excType.__name__  # type: ignore - excType is not None

    return {
        "type": excTypeName,
        "message": excMessage,
        "fileName": fileName,
        "lineNumber": lineNumber,
        "process": multiprocessing.current_process().name,
    }
