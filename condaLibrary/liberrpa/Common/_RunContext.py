# FileName: _RunContext.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from datetime import datetime
from enum import StrEnum
import math
import json
import os
from pathlib import Path
from uuid import UUID
from dataclasses import dataclass
from functools import cache
from itertools import chain
from typing import NotRequired, TypedDict, cast

from liberrpa.Common._TypedValue import JsonValue


class OutputSnapshotStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class OutputSnapshot(TypedDict):
    status: OutputSnapshotStatus
    values: list[tuple[str, JsonValue]] | None
    unavailableKeys: list[str]
    reason: str


class EmailOutputStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    LIMIT = "limit"
    UNAVAILABLE = "unavailable"


class EmailOutputKeys(TypedDict):
    completed: list[str]
    error: list[str]


class EmailOutputItem(TypedDict):
    key: str
    status: EmailOutputStatus
    text: str


class ExecutionErrorSummary(TypedDict):
    type: str
    message: str


INT_MAX_CUSTOM_ARGS_BYTES = 64 * 1024
_INT_MAX_JSON_DEPTH = 64
_INT_MAX_EMAIL_OUTPUT_BYTES = 64 * 1024
_INT_MAX_SAFE_INTEGER = 2**53 - 1
_INT_MAX_ERROR_MESSAGE_LENGTH = 2000


class ExecutorRunStateStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass(frozen=True, slots=True)
class ExecutorRunContext:
    runId: str
    runStatePath: Path
    projectName: str
    projectVersion: str
    startedAt: datetime


class ExecutorRunState(TypedDict):
    schemaVersion: int
    runId: str
    projectName: str
    projectVersion: str
    startedAt: str
    logPath: str
    status: ExecutorRunStateStatus
    endedAt: NotRequired[str]
    outputs: NotRequired[OutputSnapshot]
    errorSummary: NotRequired[ExecutionErrorSummary | None]
    emailOutputContext: NotRequired[list[EmailOutputItem] | None]


_ENV_RUN_STARTED_AT = "LIBERRPA_RUN_STARTED_AT"
_ENV_EXECUTOR_RUN_ID = "LIBERRPA_EXECUTOR_RUN_ID"
_ENV_EXECUTOR_RUN_STATE_PATH = "LIBERRPA_EXECUTOR_RUN_STATE_PATH"
_ENV_EXECUTOR_PROJECT_NAME = "LIBERRPA_EXECUTOR_PROJECT_NAME"
_ENV_EXECUTOR_PROJECT_VERSION = "LIBERRPA_EXECUTOR_PROJECT_VERSION"


class _JsonLimitError(ValueError):
    pass


def _validate_json_value(
    value: object, depth: int = 0, ancestorIds: set[int] | None = None
) -> None:
    if depth > _INT_MAX_JSON_DEPTH:
        raise _JsonLimitError("JSON must not exceed 64 levels of nesting.")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if abs(value) > _INT_MAX_SAFE_INTEGER:
            raise ValueError("The integer exceeds the shared safe JSON integer range.")
        return
    if type(value) is float:
        if not math.isfinite(value) or (
            value.is_integer() and abs(value) > _INT_MAX_SAFE_INTEGER
        ):
            raise ValueError("The number is not a finite safe JSON number.")
        return
    if type(value) is str:
        if "\0" in value:
            raise ValueError("JSON text must not contain NUL characters.")
        value.encode("utf-8")
        return
    if type(value) not in (list, dict):
        raise ValueError("The value is not ordinary JSON.")

    if ancestorIds is None:
        ancestorIds = set()
    intValueId = id(value)
    if intValueId in ancestorIds:
        raise ValueError("JSON must not contain circular references.")
    ancestorIds.add(intValueId)
    try:
        if type(value) is list:
            for child in value:
                _validate_json_value(child, depth + 1, ancestorIds)
        elif type(value) is dict:
            for strKey, child in value.items():
                if type(strKey) is not str:
                    raise ValueError("JSON object keys must be strings.")
                if "\0" in strKey:
                    raise ValueError("JSON object keys must not contain NUL characters.")
                strKey.encode("utf-8")
                _validate_json_value(child, depth + 1, ancestorIds)
    finally:
        ancestorIds.remove(intValueId)


def serialize_bounded_json(
    value: object, intMaxBytes: int = INT_MAX_CUSTOM_ARGS_BYTES
) -> str:
    listPart: list[str] = []
    intBytes = 0
    encoderObj = json.JSONEncoder(
        ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )
    for strPart in encoderObj.iterencode(value):
        intBytes += len(strPart.encode("utf-8"))
        if intBytes > intMaxBytes:
            raise _JsonLimitError(f"JSON exceeds the {intMaxBytes}-byte limit.")
        listPart.append(strPart)
    return "".join(listPart)


def capture_output_snapshot(
    customArgs: object, emailOutputKeys: list[str]
) -> tuple[OutputSnapshot, list[EmailOutputItem] | None]:
    """Capture business outputs and independent email references in one pass."""
    unavailableSnapshot: OutputSnapshot = {
        "status": OutputSnapshotStatus.UNAVAILABLE,
        "values": None,
        "unavailableKeys": [],
        "reason": "Final CustomArgs could not be captured within the shared JSON limits.",
    }
    try:
        dictEmailItem: dict[str, EmailOutputItem] = {
            strKey: {"key": strKey, "status": EmailOutputStatus.MISSING, "text": ""}
            for strKey in emailOutputKeys
        }
        if type(customArgs) is not dict:
            return unavailableSnapshot, None if emailOutputKeys else []

        boolOutputsAvailable = True
        dictValuePart: dict[str, str] = {}
        intValuesBytes = 2
        setUnavailableKey: set[str] = set()
        intEmailBytes = 0
        # Allocate email capacity in template order while capturing each value only once.
        for strKey in chain(
            emailOutputKeys, (key for key in customArgs if key not in dictEmailItem)
        ):
            if strKey not in customArgs:
                continue
            value = customArgs[strKey]
            try:
                if type(strKey) is not str or "\0" in strKey:
                    raise ValueError("Final CustomArgs contains an invalid key.")
                strKey.encode("utf-8")
            except (ValueError, UnicodeError):
                boolOutputsAvailable = False
                continue

            emailItem = dictEmailItem.get(strKey)
            if not boolOutputsAvailable and emailItem is None:
                continue
            try:
                # Include the ordered list and each [key, value] pair in the shared depth limit.
                _validate_json_value(value, depth=2)
            except _JsonLimitError:
                if boolOutputsAvailable:
                    setUnavailableKey.add(strKey)
                if emailItem is not None:
                    emailItem["status"] = EmailOutputStatus.LIMIT
                continue
            except (ValueError, UnicodeError, RecursionError):
                if boolOutputsAvailable:
                    setUnavailableKey.add(strKey)
                if emailItem is not None:
                    emailItem["status"] = EmailOutputStatus.UNAVAILABLE
                continue

            boolCaptureOutput = boolOutputsAvailable
            boolCaptureEmail = emailItem is not None

            intRemainingBytes = 0
            strKeyJson = ""
            intPairBytes = 0
            if boolCaptureOutput:
                strKeyJson = json.dumps(strKey, ensure_ascii=False)
                intPairBytes = len(strKeyJson.encode("utf-8")) + 3 + bool(dictValuePart)
                intRemainingBytes = (
                    INT_MAX_CUSTOM_ARGS_BYTES - intValuesBytes - intPairBytes
                )
                if intRemainingBytes < 0:
                    boolOutputsAvailable = boolCaptureOutput = False
            if not boolCaptureOutput and not boolCaptureEmail:
                continue

            try:
                strValue = serialize_bounded_json(
                    value,
                    max(
                        intRemainingBytes if boolCaptureOutput else 0,
                        _INT_MAX_EMAIL_OUTPUT_BYTES - intEmailBytes
                        if boolCaptureEmail
                        else 0,
                    ),
                )
            except _JsonLimitError:
                if boolCaptureOutput:
                    boolOutputsAvailable = False
                if emailItem is not None and boolCaptureEmail:
                    emailItem["status"] = EmailOutputStatus.LIMIT
                continue

            intValueBytes = len(strValue.encode("utf-8"))
            if boolCaptureOutput:
                if intValueBytes > intRemainingBytes:
                    boolOutputsAvailable = False
                else:
                    dictValuePart[strKey] = f"[{strKeyJson},{strValue}]"
                    intValuesBytes += intPairBytes + intValueBytes
            if emailItem is not None and boolCaptureEmail:
                if intEmailBytes + intValueBytes > _INT_MAX_EMAIL_OUTPUT_BYTES:
                    emailItem["status"] = EmailOutputStatus.LIMIT
                else:
                    emailItem["status"] = EmailOutputStatus.AVAILABLE
                    emailItem["text"] = strValue
                    intEmailBytes += intValueBytes

        emailOutputContext = list(dictEmailItem.values())

        if not boolOutputsAvailable:
            return unavailableSnapshot, emailOutputContext
        listUnavailableKey = [
            strKey for strKey in customArgs if strKey in setUnavailableKey
        ]
        try:
            # Keep unavailable names bounded without silently dropping them.
            serialize_bounded_json(listUnavailableKey)
        except _JsonLimitError:
            return unavailableSnapshot, emailOutputContext
        listValuePart = [
            dictValuePart[strKey] for strKey in customArgs if strKey in dictValuePart
        ]
        return {
            "status": (
                OutputSnapshotStatus.PARTIAL
                if listUnavailableKey
                else OutputSnapshotStatus.COMPLETE
            ),
            "values": [
                (strKey, value)
                for strKey, value in json.loads("[" + ",".join(listValuePart) + "]")
            ],
            "unavailableKeys": listUnavailableKey,
            "reason": (
                "Some final CustomArgs values are not ordinary JSON."
                if listUnavailableKey
                else ""
            ),
        }, emailOutputContext
    except Exception:
        return unavailableSnapshot, None if emailOutputKeys else []


def capture_execution_error(errorObj: Exception | None) -> ExecutionErrorSummary | None:
    """Summarize only the exception recorded as the final unhandled execution error."""
    if errorObj is None:
        return None
    try:
        strMessage = str(errorObj)[:_INT_MAX_ERROR_MESSAGE_LENGTH]
        strMessage = strMessage.encode("utf-8", errors="replace").decode("utf-8")
        return {"type": type(errorObj).__name__, "message": strMessage}
    except Exception:
        return {"type": type(errorObj).__name__, "message": "Error message unavailable."}


def _parse_datetime(value: str, variableName: str) -> datetime:
    try:
        datetimeValue = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Invalid {variableName}: {value!r}")

    if datetimeValue.tzinfo is None:
        raise ValueError(f"{variableName} must include a timezone: {value!r}")

    return datetimeValue.astimezone()


@cache
def get_or_create_run_started_at() -> datetime:
    strStartedAt = os.getenv(_ENV_RUN_STARTED_AT)

    if strStartedAt is not None:
        return _parse_datetime(strStartedAt, _ENV_RUN_STARTED_AT)

    datetimeStartedAt = datetime.now().astimezone()
    os.environ[_ENV_RUN_STARTED_AT] = datetimeStartedAt.isoformat(timespec="microseconds")
    return datetimeStartedAt


@cache
def get_executor_run_context() -> ExecutorRunContext | None:
    dictValues = {
        _ENV_EXECUTOR_RUN_ID: os.getenv(_ENV_EXECUTOR_RUN_ID),
        _ENV_EXECUTOR_RUN_STATE_PATH: os.getenv(_ENV_EXECUTOR_RUN_STATE_PATH),
        _ENV_EXECUTOR_PROJECT_NAME: os.getenv(_ENV_EXECUTOR_PROJECT_NAME),
        _ENV_EXECUTOR_PROJECT_VERSION: os.getenv(_ENV_EXECUTOR_PROJECT_VERSION),
    }

    if all(value is None for value in dictValues.values()):
        return None

    listMissing = [name for name, value in dictValues.items() if value is None]
    if listMissing:
        raise RuntimeError(
            f"Incomplete Executor run context. Missing environment variable(s): {listMissing}"
        )

    strRunId = cast(str, dictValues[_ENV_EXECUTOR_RUN_ID])
    strRunStatePath = cast(str, dictValues[_ENV_EXECUTOR_RUN_STATE_PATH])
    strProjectName = cast(str, dictValues[_ENV_EXECUTOR_PROJECT_NAME])
    strProjectVersion = cast(str, dictValues[_ENV_EXECUTOR_PROJECT_VERSION])

    try:
        UUID(strRunId)
    except ValueError:
        raise ValueError(f"Invalid {_ENV_EXECUTOR_RUN_ID}: {strRunId!r}")

    if not strProjectName.strip():
        raise ValueError(f"{_ENV_EXECUTOR_PROJECT_NAME} cannot be empty.")

    if not strProjectVersion.strip():
        raise ValueError(f"{_ENV_EXECUTOR_PROJECT_VERSION} cannot be empty.")

    pathRunState = Path(strRunStatePath)
    if not pathRunState.is_absolute():
        raise ValueError(
            f"{_ENV_EXECUTOR_RUN_STATE_PATH} must be an absolute path: {strRunStatePath!r}"
        )

    return ExecutorRunContext(
        runId=strRunId,
        runStatePath=pathRunState,
        projectName=strProjectName,
        projectVersion=strProjectVersion,
        startedAt=get_or_create_run_started_at(),
    )


def _build_executor_run_state(
    contextObj: ExecutorRunContext,
    status: ExecutorRunStateStatus,
    logPath: str,
) -> ExecutorRunState:
    dictState: ExecutorRunState = {
        "schemaVersion": 1,
        "runId": contextObj.runId,
        "projectName": contextObj.projectName,
        "projectVersion": contextObj.projectVersion,
        "startedAt": contextObj.startedAt.isoformat(timespec="microseconds"),
        "logPath": logPath,
        "status": status,
    }

    if status != ExecutorRunStateStatus.RUNNING:
        dictState["endedAt"] = (
            datetime.now().astimezone().isoformat(timespec="microseconds")
        )

    return dictState


def build_executor_run_state(
    status: ExecutorRunStateStatus,
    logPath: str,
) -> ExecutorRunState | None:
    contextObj = get_executor_run_context()
    if contextObj is None:
        return None

    return _build_executor_run_state(
        contextObj=contextObj,
        status=status,
        logPath=logPath,
    )


def write_executor_run_state(
    status: ExecutorRunStateStatus,
    logPath: str,
    outputs: OutputSnapshot | None = None,
    errorSummary: ExecutionErrorSummary | None = None,
    emailOutputContext: list[EmailOutputItem] | None = None,
) -> None:
    contextObj = get_executor_run_context()
    if contextObj is None:
        return

    dictState = _build_executor_run_state(
        contextObj=contextObj,
        status=status,
        logPath=logPath,
    )

    if status != ExecutorRunStateStatus.RUNNING:
        if outputs is not None:
            dictState["outputs"] = outputs
        dictState["emailOutputContext"] = emailOutputContext
        dictState["errorSummary"] = (
            errorSummary if status == ExecutorRunStateStatus.ERROR else None
        )

    pathRunState = contextObj.runStatePath
    pathTemp = pathRunState.with_name(f".{pathRunState.name}.{os.getpid()}.tmp")

    try:
        pathTemp.write_text(
            json.dumps(dictState, indent=4, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
            errors="strict",
        )
        pathTemp.replace(pathRunState)
    finally:
        if pathTemp.exists():
            pathTemp.unlink()
