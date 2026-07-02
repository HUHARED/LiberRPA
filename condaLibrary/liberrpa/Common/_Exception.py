# FileName: _Exception.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.Common._Utils import PROCESS_NAME

import traceback
from typing import TypedDict


class UiElementNotFoundError(Exception):
    """Custom exception for UI not found"""

    def __init__(self, message="Not found the target element.", *args):
        super().__init__(message, *args)


class UiTimeoutError(Exception):
    """Custom exception for UI operation timeout"""

    def __init__(self, message="Timeout for UI operation exceeded.", *args):
        super().__init__(message, *args)


class UiWaitTimeoutError(UiTimeoutError):
    """Base exception for UI wait timeout."""

    def __init__(self, message="Timeout for UI wait operation exceeded.", *args):
        super().__init__(message, *args)


class UiElementAppearTimeoutError(UiWaitTimeoutError):
    """Timeout while waiting for a UI element to appear."""

    def __init__(self, message="Timeout exceeded for UI element to appear.", *args):
        super().__init__(message, *args)


class UiElementDisappearTimeoutError(UiWaitTimeoutError):
    """Timeout while waiting for a UI element to disappear."""

    def __init__(self, message="Timeout exceeded for UI element to disappear.", *args):
        super().__init__(message, *args)


class UiUnsafeThreadTerminationError(UiTimeoutError):
    """Unsafe timeout fallback injected an exception into a worker thread."""

    def __init__(
        self,
        message="Unsafe UI timeout fallback was triggered. A worker thread was forcibly interrupted.",
        *args,
    ):
        super().__init__(message, *args)


class UiUnstoppableThreadError(UiUnsafeThreadTerminationError):
    """Unsafe timeout fallback was triggered, but the worker thread did not stop."""

    def __init__(
        self,
        message=(
            "Unsafe UI timeout fallback was triggered, but the worker thread did not stop.\nThe current Python process may be in an unsafe state."
        ),
        *args,
    ):
        super().__init__(message, *args)


class UiSelectorError(ValueError):
    """Invalid UI selector structure or selector value."""

    def __init__(self, message="Invalid UI selector.", *args):
        super().__init__(message, *args)


class UiOperationError(Exception):
    """Custom exception for unsupported or failed UI operations."""

    def __init__(self, message="Failed to perform the UI operation.", *args):
        super().__init__(message, *args)


class ChromeCommandError(Exception):
    """Custom exception for Chrome manipulation."""

    def __init__(self, message="Error when manipulating Chrome.", *args):
        super().__init__(message, *args)


class ChromeElementNotFoundError(ChromeCommandError):
    """Chrome command succeeded, but the target HTML element was not found."""

    def __init__(self, message="Not found the target element in Chrome.", *args):
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
    excTraceback = ex.__traceback__

    if excTraceback is not None:
        lastFrame = traceback.extract_tb(excTraceback)[-1]
        fileName = lastFrame.filename
        lineNumber = lastFrame.lineno
    else:
        fileName = ""
        lineNumber = None

    return {
        "type": type(ex).__name__,
        "message": str(ex),
        "fileName": fileName,
        "lineNumber": lineNumber,
        "process": PROCESS_NAME,
    }
