# FileName: logging.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import errno
import logging
import os
import re
import subprocess
import time
import uuid
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from pathlib import Path
from smtplib import SMTPResponseException
from tempfile import TemporaryFile
from traceback import walk_tb
from types import TracebackType
from typing import get_args

from pydantic import BaseModel, ValidationError
from pydantic_core.core_schema import ErrorType
from psycopg import Error as PsycopgError

_REQUEST_ID: ContextVar[uuid.UUID | None] = ContextVar("console_request_id", default=None)

_INT_VALIDATION_ERROR_LIMIT = 8
_SET_VALIDATION_ERROR_TYPE = frozenset(get_args(ErrorType))

_INT_COMMAND_DIAGNOSTIC_BYTES = 16384
_INT_COMMAND_DIAGNOSTIC_LENGTH = 2000
_COMMAND_DIAGNOSTIC_PREFIX = re.compile(
    r"^(?:(?:pg_dump|pg_restore|initdb): (?:error|fatal):"
    r"|psql:(?:[^:\r\n]*:)*\s*(?:error|fatal):"
    r"|(?:error|fatal|panic):|pg_ctl:|runuser:"
    r"|(?:connection failed: )?connection to server)",
    re.IGNORECASE,
)
_QUOTED_DIAGNOSTIC_VALUE = re.compile(
    r"\"(?:[^\"\\]|\\.)*(?:\"|$)|'(?:[^'\\]|\\.)*(?:'|$)"
)


def get_exception_summary(error: BaseException) -> str:
    """Describe the error without its message, command arguments, or file contents."""
    listDetail = [type(error).__name__]
    if isinstance(error, ValidationError):
        # Validation locations can contain user keys; only declared field names and aliases are public.
        setFieldName: set[str] = set()
        setModelClass: set[type[BaseModel]] = set()
        listModelClass = [BaseModel]
        while listModelClass:
            modelClass = listModelClass.pop()
            if modelClass in setModelClass:
                continue
            setModelClass.add(modelClass)
            for strFieldName, fieldInfo in modelClass.model_fields.items():
                setFieldName.add(strFieldName)
                if fieldInfo.alias is not None:
                    setFieldName.add(fieldInfo.alias)
            listModelClass.extend(modelClass.__subclasses__())

        intErrorCount = error.error_count()
        listDetail.append(f"Validation errors: {intErrorCount}")
        for detail in error.errors(
            include_url=False, include_input=False, include_context=False
        )[:_INT_VALIDATION_ERROR_LIMIT]:
            strPath = ".".join(
                str(part) if isinstance(part, int) or part in setFieldName else "[key]"
                for part in detail["loc"]
            )
            strErrorType = (
                detail["type"]
                if detail["type"] in _SET_VALIDATION_ERROR_TYPE
                else "custom_error"
            )
            listDetail.append(f"{strPath or '<root>'}: {strErrorType}")
        if intErrorCount > _INT_VALIDATION_ERROR_LIMIT:
            listDetail.append("Additional validation errors omitted")
    if isinstance(error, OSError) and error.errno is not None:
        strCode = errno.errorcode.get(error.errno, "UNKNOWN")
        listDetail.append(
            f"OS error {error.errno} ({strCode}): {os.strerror(error.errno)}"
        )
    intWinError = getattr(error, "winerror", None)
    if isinstance(intWinError, int):
        listDetail.append(f"Windows error {intWinError}")
    if isinstance(error, PsycopgError):
        if error.sqlstate is not None:
            listDetail.append(f"PostgreSQL SQLSTATE {error.sqlstate}")
        else:
            # Connection errors often have no SQLSTATE; report fixed reasons, not libpq's connection text.
            strError = str(error).lower()
            for strMarker, strReason in (
                (
                    "password authentication failed",
                    "Database password authentication failed",
                ),
                ("no password supplied", "The database password was not supplied"),
                (
                    "could not translate host name",
                    "The database host could not be resolved",
                ),
                ("connection refused", "The database connection was refused"),
                ("timeout expired", "The database connection timed out"),
            ):
                if strMarker in strError:
                    listDetail.append(strReason)
                    break
            else:
                if re.search(
                    r"FATAL:\s+database .+ does not exist", strError, re.IGNORECASE
                ):
                    listDetail.append("The configured database does not exist")
    if isinstance(error, SMTPResponseException):
        listDetail.append(f"SMTP status {error.smtp_code}")
    if isinstance(error, subprocess.CalledProcessError):
        listDetail.append(f"exit code {error.returncode}")
    return "; ".join(listDetail)


def _format_command_diagnostics(content: bytes, secrets: Iterable[str]) -> str:
    """Keep bounded primary PostgreSQL errors, never SQL excerpts or row details."""
    boolTruncated = len(content) > _INT_COMMAND_DIAGNOSTIC_BYTES
    if boolTruncated:
        # Drop an incomplete last line before redaction rather than exposing part of a secret.
        content = content[:_INT_COMMAND_DIAGNOSTIC_BYTES]
        content = content.rsplit(b"\n", 1)[0] if b"\n" in content else b""
    strOutput = content.decode("utf-8", errors="replace")
    setSecret = {
        variant
        for secret in secrets
        if secret
        for variant in (
            secret,
            secret.replace("'", "''"),
            secret.replace("\\", "\\\\").replace("'", "\\'"),
        )
    }
    for strSecret in sorted(setSecret, key=len, reverse=True):
        strOutput = strOutput.replace(strSecret, "[redacted]")
    strDiagnostic = "No safe primary diagnostic was available."
    for strLine in strOutput.splitlines():
        strLine = strLine.strip()
        if not _COMMAND_DIAGNOSTIC_PREFIX.match(strLine):
            continue
        # Keep only the first primary error, not subsequent SQL, COPY rows, or server detail/context.
        strLine = re.split(
            r"\b(?:DETAIL|CONTEXT|STATEMENT|HINT|Command was|Query was|LINE \d+):",
            strLine,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        strLine = _QUOTED_DIAGNOSTIC_VALUE.sub("[redacted]", strLine)
        strLine = re.sub(
            r"postgres(?:ql)?://\S+", "[redacted]", strLine, flags=re.IGNORECASE
        )
        strLine = re.sub(
            r"\b(password\s*[=:]\s*)\S+",
            r"\1[redacted]",
            strLine,
            flags=re.IGNORECASE,
        )
        strDiagnostic = "".join(
            character if character.isprintable() else " " for character in strLine
        )
        break
    if len(strDiagnostic) > _INT_COMMAND_DIAGNOSTIC_LENGTH:
        strDiagnostic = strDiagnostic[:_INT_COMMAND_DIAGNOSTIC_LENGTH]
        boolTruncated = True
    return strDiagnostic + (
        "\nAdditional command output omitted." if boolTruncated else ""
    )


@contextmanager
def capture_command_errors(
    logger: logging.Logger,
    commandName: str,
    *,
    secrets: Iterable[str] = (),
) -> Generator[int]:
    """Yield a stderr file descriptor and report a safe excerpt only when a checked command fails."""
    with TemporaryFile(mode="w+b") as output:
        try:
            yield output.fileno()
        except subprocess.CalledProcessError as e:
            output.seek(0)
            strDiagnostic = _format_command_diagnostics(
                output.read(_INT_COMMAND_DIAGNOSTIC_BYTES + 1), secrets
            )
            logger.error(
                "%s failed (exit code %s).\n%s", commandName, e.returncode, strDiagnostic
            )
            raise


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
        listDetail: list[str] = []
        setSeen: set[int] = set()
        tracebackObj = exceptionInfo[2]
        while error is not None and id(error) not in setSeen:
            setSeen.add(id(error))
            listDetail.append(get_exception_summary(error) + ".")
            if isinstance(error, AttributeError):
                if error.name is not None and error.name.isidentifier():
                    listDetail.append(f"Missing attribute: {error.name}.")
                if error.obj is not None:
                    listDetail.append(f"Object type: {type(error.obj).__name__}.")
            # Standard error codes explain failures without exception messages, SQL, SMTP replies, or frame locals.
            if tracebackObj is not None:
                for tracebackFrame, intLineNumber in walk_tb(tracebackObj):
                    codeObj = tracebackFrame.f_code
                    listDetail.append(
                        f"  {Path(codeObj.co_filename).name}:{intLineNumber} in {codeObj.co_name}"
                    )
            if error.__cause__ is not None:
                error = error.__cause__
                strRelation = "Caused by:"
            elif not error.__suppress_context__ and error.__context__ is not None:
                error = error.__context__
                strRelation = "While handling:"
            else:
                break
            if id(error) not in setSeen:
                listDetail.append(strRelation)
            tracebackObj = error.__traceback__
        return "\n".join(listDetail)

    def format(self, record: logging.LogRecord) -> str:
        logRecord = copy(record)
        logRecord.requestId = str(get_request_id() or "-")
        # Django error messages can contain URLs, Host headers, SQL, or exception text.
        if logRecord.name.startswith("django."):
            intStatusCode = getattr(logRecord, "status_code", None)
            strStatus = (
                f" status={intStatusCode}"
                if isinstance(intStatusCode, int) and 100 <= intStatusCode <= 599
                else ""
            )
            logRecord.msg = (
                f"Django diagnostic{strStatus} at {logRecord.filename}:"
                f"{logRecord.lineno} in {logRecord.funcName}."
            )
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
                "request=%(requestId)s %(message)s",
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
