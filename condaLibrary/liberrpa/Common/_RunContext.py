# FileName: _RunContext.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from datetime import datetime
import json
import os
from pathlib import Path
from uuid import UUID
from dataclasses import dataclass
from functools import cache
from typing import Literal, NotRequired, TypedDict, cast


type ExecutorRunStateStatus = Literal["running", "completed", "error", "terminated"]


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
    status: ExecutorRunStateStatus
    endedAt: NotRequired[str]


_ENV_RUN_STARTED_AT = "LIBERRPA_RUN_STARTED_AT"
_ENV_EXECUTOR_RUN_ID = "LIBERRPA_EXECUTOR_RUN_ID"
_ENV_EXECUTOR_RUN_STATE_PATH = "LIBERRPA_EXECUTOR_RUN_STATE_PATH"
_ENV_EXECUTOR_PACKAGE_NAME = "LIBERRPA_EXECUTOR_PACKAGE_NAME"
_ENV_EXECUTOR_PACKAGE_VERSION = "LIBERRPA_EXECUTOR_PACKAGE_VERSION"


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
        raise RuntimeError(f"Incomplete Executor run context. Missing environment variable(s): {listMissing}")

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
        raise ValueError(f"{_ENV_EXECUTOR_RUN_STATE_PATH} must be an absolute path: {strRunStatePath!r}")

    return ExecutorRunContext(
        runId=strRunId,
        runStatePath=pathRunState,
        packageName=strPackageName,
        packageVersion=strPackageVersion,
        startedAt=get_or_create_run_started_at(),
    )


def write_executor_run_state(status: ExecutorRunStateStatus, logPath: str) -> None:
    contextObj = get_executor_run_context()
    if contextObj is None:
        return

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
        dictState["endedAt"] = datetime.now().astimezone().isoformat(timespec="microseconds")

    pathRunState = contextObj.runStatePath
    pathTemp = pathRunState.with_name(f".{pathRunState.name}.{os.getpid()}.tmp")

    try:
        pathTemp.write_text(
            json.dumps(dictState, indent=4, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
            errors="strict",
        )
        pathTemp.replace(pathRunState)
        print(pathRunState)
    finally:
        if pathTemp.exists():
            pathTemp.unlink()
