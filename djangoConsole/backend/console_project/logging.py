# FileName: logging.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from pathlib import Path
from traceback import walk_tb
from types import TracebackType

_REQUEST_ID: ContextVar[uuid.UUID | None] = ContextVar("console_request_id", default=None)


def get_request_id() -> uuid.UUID | None:
    return _REQUEST_ID.get()


@contextmanager
def request_log_context() -> Generator[uuid.UUID]:
    """Generate our own correlation ID; client headers never select a log identity."""
    requestId = uuid.uuid4()
    contextToken = _REQUEST_ID.set(requestId)
    try:
        yield requestId
    finally:
        _REQUEST_ID.reset(contextToken)


class RequestExceptionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # The middleware already logs response summaries, including handled failures.
        return record.exc_info is not None


class ConsoleFormatter(logging.Formatter):
    """Format UTC diagnostics without dumping request data or exception values."""

    converter = time.gmtime

    def formatException(
        self,
        exceptionInfo: tuple[type[BaseException], BaseException, TracebackType | None]
        | tuple[None, None, None],
    ) -> str:
        error = exceptionInfo[1]
        if error is None:
            return ""
        listDetail = [f"Exception type: {type(error).__name__}."]
        if isinstance(error, AttributeError):
            if error.name is not None and error.name.isidentifier():
                listDetail.append(f"Missing attribute: {error.name}.")
            if error.obj is not None:
                listDetail.append(f"Object type: {type(error.obj).__name__}.")
        # No exception messages, source lines, argument values, or frame locals.
        if exceptionInfo[2] is not None:
            for tracebackFrame, intLineNumber in walk_tb(exceptionInfo[2]):
                codeObj = tracebackFrame.f_code
                listDetail.append(
                    f"  {Path(codeObj.co_filename).name}:{intLineNumber} in {codeObj.co_name}"
                )
        return "\n".join(listDetail)

    def format(self, record: logging.LogRecord) -> str:
        logRecord = copy(record)
        logRecord.request_id = str(get_request_id() or "-")
        # Django error messages can contain URLs, Host headers, SQL, or exception text.
        if logRecord.name.startswith("django."):
            logRecord.msg = "Django diagnostic."
            logRecord.args = ()
        logRecord.exc_text = None
        logRecord.stack_info = None
        return super().format(logRecord)


def build_logging_config(level: str) -> dict[str, object]:
    """Use one stream for application, Django, and worker diagnostics."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "()": ConsoleFormatter,
                "format": "%(asctime)s.%(msecs)03dZ %(levelname)s %(name)s "
                "request=%(request_id)s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            }
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "console"},
            "null": {"class": "logging.NullHandler"},
        },
        "filters": {"request_exception": {"()": RequestExceptionFilter}},
        "root": {"handlers": ["console"], "level": "WARNING"},
        "loggers": {
            "console": {"handlers": ["console"], "level": level, "propagate": False},
            "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
            "django.request": {
                "handlers": ["console"],
                "level": "ERROR",
                "filters": ["request_exception"],
                "propagate": False,
            },
            "django.server": {"handlers": ["null"], "propagate": False},
            "django.db.backends": {"level": "WARNING"},
            "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
            # Our request summary replaces raw access URLs, which may contain email tokens.
            "uvicorn.access": {"handlers": ["null"], "propagate": False},
        },
    }
