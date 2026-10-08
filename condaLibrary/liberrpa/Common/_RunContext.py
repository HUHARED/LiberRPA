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
from typing import Literal, NotRequired, TypedDict, cast

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


class ExecutionErrorSummary(TypedDict):
    type: str
    message: str


_INT_MAX_CUSTOM_ARGS_BYTES = 64 * 1024
_INT_MAX_JSON_DEPTH = 64
_INT_MAX_SAFE_INTEGER = 2**53 - 1
_INT_MAX_ERROR_MESSAGE_LENGTH = 2000


type Str_ExecutorRunStateStatus = Literal["running", "completed", "error", "terminated"]


@dataclass(frozen=True, slots=True)
class ExecutorRunContext:
    runId: str
    runStatePath: Path
    packageName: str
    packageVersion: str
    startedAt: datetime


class DictExecutorRunState(TypedDict):
    schemaVersion: int
    runId: str
    packageName: str
    packageVersion: str
    startedAt: str
    logPath: str
    status: Str_ExecutorRunStateStatus
    endedAt: NotRequired[str]
    outputs: NotRequired[OutputSnapshot]
    errorSummary: NotRequired[ExecutionErrorSummary | None]


_ENV_RUN_STARTED_AT = "LIBERRPA_RUN_STARTED_AT"
_ENV_EXECUTOR_RUN_ID = "LIBERRPA_EXECUTOR_RUN_ID"
_ENV_EXECUTOR_RUN_STATE_PATH = "LIBERRPA_EXECUTOR_RUN_STATE_PATH"
_ENV_EXECUTOR_PACKAGE_NAME = "LIBERRPA_EXECUTOR_PACKAGE_NAME"
_ENV_EXECUTOR_PACKAGE_VERSION = "LIBERRPA_EXECUTOR_PACKAGE_VERSION"


def _validate_json_value(value: object, depth: int = 0) -> None:
    if depth > _INT_MAX_JSON_DEPTH:
        raise ValueError("JSON must not exceed 64 levels of nesting.")
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
    if type(value) is list:
        for child in value:
            _validate_json_value(child, depth + 1)
        return
    if type(value) is dict:
        for strKey, child in value.items():
            if type(strKey) is not str:
                raise ValueError("JSON object keys must be strings.")
            if "\0" in strKey:
                raise ValueError("JSON object keys must not contain NUL characters.")
            strKey.encode("utf-8")
            _validate_json_value(child, depth + 1)
        return
    raise ValueError("The value is not ordinary JSON.")


def _serialize_bounded_json(value: object) -> str:
    listPart: list[str] = []
    intBytes = 0
    encoderObj = json.JSONEncoder(
        ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )
    for strPart in encoderObj.iterencode(value):
        intBytes += len(strPart.encode("utf-8"))
        if intBytes > _INT_MAX_CUSTOM_ARGS_BYTES:
            raise ValueError("The CustomArgs snapshot exceeds 64 KiB.")
        listPart.append(strPart)
    return "".join(listPart)


def capture_output_snapshot(customArgs: object) -> OutputSnapshot:
    """Capture final ordinary JSON values without changing the actual execution result."""
    try:
        if type(customArgs) is not dict:
            raise ValueError("Final CustomArgs is not a dictionary.")
        listValue: list[tuple[str, object]] = []
        listUnavailableKey: list[str] = []
        for strKey, value in customArgs.items():
            if type(strKey) is not str:
                raise ValueError("Final CustomArgs contains a non-string key.")
            if "\0" in strKey:
                raise ValueError("Final CustomArgs contains a NUL character in a key.")
            strKey.encode("utf-8")
            try:
                # Count from the ordered list and its [key, value] pair, as for inputs.
                _validate_json_value(value, 2)
            except (ValueError, UnicodeError, RecursionError):
                listUnavailableKey.append(strKey)
            else:
                listValue.append((strKey, value))
        strValues = _serialize_bounded_json(listValue)
        # Keep diagnostic metadata bounded too, without silently dropping unavailable names.
        _serialize_bounded_json(listUnavailableKey)
        return {
            "status": (
                OutputSnapshotStatus.PARTIAL
                if listUnavailableKey
                else OutputSnapshotStatus.COMPLETE
            ),
            "values": [(strKey, value) for strKey, value in json.loads(strValues)],
            "unavailableKeys": listUnavailableKey,
            "reason": (
                "Some final CustomArgs values are not ordinary JSON."
                if listUnavailableKey
                else ""
            ),
        }
    except Exception:
        return {
            "status": OutputSnapshotStatus.UNAVAILABLE,
            "values": None,
            "unavailableKeys": [],
            "reason": "Final CustomArgs could not be captured within the shared JSON limits.",
        }


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
        _ENV_EXECUTOR_PACKAGE_NAME: os.getenv(_ENV_EXECUTOR_PACKAGE_NAME),
        _ENV_EXECUTOR_PACKAGE_VERSION: os.getenv(_ENV_EXECUTOR_PACKAGE_VERSION),
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
    strPackageName = cast(str, dictValues[_ENV_EXECUTOR_PACKAGE_NAME])
    strPackageVersion = cast(str, dictValues[_ENV_EXECUTOR_PACKAGE_VERSION])

    try:
        UUID(strRunId)
    except ValueError:
        raise ValueError(f"Invalid {_ENV_EXECUTOR_RUN_ID}: {strRunId!r}")

    if not strPackageName.strip():
        raise ValueError(f"{_ENV_EXECUTOR_PACKAGE_NAME} cannot be empty.")

    if not strPackageVersion.strip():
        raise ValueError(f"{_ENV_EXECUTOR_PACKAGE_VERSION} cannot be empty.")

    pathRunState = Path(strRunStatePath)
    if not pathRunState.is_absolute():
        raise ValueError(
            f"{_ENV_EXECUTOR_RUN_STATE_PATH} must be an absolute path: {strRunStatePath!r}"
        )

    return ExecutorRunContext(
        runId=strRunId,
        runStatePath=pathRunState,
        packageName=strPackageName,
        packageVersion=strPackageVersion,
        startedAt=get_or_create_run_started_at(),
    )


def _build_executor_run_state(
    contextObj: ExecutorRunContext,
    status: Str_ExecutorRunStateStatus,
    logPath: str,
) -> DictExecutorRunState:
    dictState: DictExecutorRunState = {
        "schemaVersion": 1,
        "runId": contextObj.runId,
        "packageName": contextObj.packageName,
        "packageVersion": contextObj.packageVersion,
        "startedAt": contextObj.startedAt.isoformat(timespec="microseconds"),
        "logPath": logPath,
        "status": status,
    }

    if status != "running":
        dictState["endedAt"] = (
            datetime.now().astimezone().isoformat(timespec="microseconds")
        )

    return dictState


def build_executor_run_state(
    status: Str_ExecutorRunStateStatus,
    logPath: str,
) -> DictExecutorRunState | None:
    contextObj = get_executor_run_context()
    if contextObj is None:
        return None

    return _build_executor_run_state(
        contextObj=contextObj,
        status=status,
        logPath=logPath,
    )


def write_executor_run_state(
    status: Str_ExecutorRunStateStatus,
    logPath: str,
    outputs: OutputSnapshot | None = None,
    errorSummary: ExecutionErrorSummary | None = None,
) -> None:
    contextObj = get_executor_run_context()
    if contextObj is None:
        return

    dictState = _build_executor_run_state(
        contextObj=contextObj,
        status=status,
        logPath=logPath,
    )

    if status != "running":
        if outputs is not None:
            dictState["outputs"] = outputs
        dictState["errorSummary"] = errorSummary if status == "error" else None

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
