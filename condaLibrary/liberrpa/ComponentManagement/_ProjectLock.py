# FileName: _ProjectLock.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement._Exception import ComponentManagementError
from liberrpa.ComponentManagement._File import read_json, serialize_json

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Iterator
import os
import time
import uuid
import psutil


_STR_LOCK_FILE_NAME = ".liberrpa-project-manager.lock"
_FLOAT_INVALID_LOCK_GRACE_SECONDS = 5.0
_FLOAT_PROCESS_CREATE_TIME_TOLERANCE = 1.0


def _is_lock_owner_active(value: object) -> bool:
    if not isinstance(value, dict):
        return False

    processId = value.get("processId")
    processCreateTime = value.get("processCreateTime")

    if type(processId) is not int or not isinstance(processCreateTime, int | float):
        return False

    try:
        processObj = psutil.Process(processId)
        return abs(processObj.create_time() - float(processCreateTime)) <= _FLOAT_PROCESS_CREATE_TIME_TOLERANCE
    except psutil.NoSuchProcess:
        return False
    except (psutil.AccessDenied, psutil.ZombieProcess):
        return True


def _try_remove_stale_lock(lockPath: Path) -> bool:
    try:
        value = read_json(lockPath)
    except (OSError, ValueError):
        try:
            floatAge = time.time() - lockPath.stat().st_mtime
        except OSError:
            return False

        if floatAge < _FLOAT_INVALID_LOCK_GRACE_SECONDS:
            return False

        lockPath.unlink(missing_ok=True)
        return True

    if _is_lock_owner_active(value):
        return False

    lockPath.unlink(missing_ok=True)
    return True


def _create_lock(lockPath: Path, operation: str) -> str:
    strOwnerId = str(uuid.uuid4())
    dictLock = {
        "schemaVersion": 1,
        "ownerId": strOwnerId,
        "processId": os.getpid(),
        "processCreateTime": psutil.Process().create_time(),
        "operation": operation,
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    bytesLock = (serialize_json(dictLock, compact=True) + "\n").encode("utf-8")

    for intAttempt in range(2):
        try:
            intFileDescriptor = os.open(lockPath, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if intAttempt == 0 and _try_remove_stale_lock(lockPath):
                continue

            raise ComponentManagementError(
                code="project_busy",
                message="Another Component operation is currently modifying this Project.",
                details={"lockFile": str(lockPath)},
            )

        with os.fdopen(intFileDescriptor, "wb", closefd=True) as fileObj:
            fileObj.write(bytesLock)
            fileObj.flush()
            os.fsync(fileObj.fileno())

        return strOwnerId

    raise ComponentManagementError(
        code="project_busy",
        message="Another Component operation is currently modifying this Project.",
        details={"lockFile": str(lockPath)},
    )


def _release_lock(lockPath: Path, ownerId: str) -> None:
    if not lockPath.exists():
        return

    try:
        value = read_json(lockPath)
    except (OSError, ValueError):
        return

    if isinstance(value, dict) and value.get("ownerId") == ownerId:
        lockPath.unlink(missing_ok=True)


@contextmanager
def project_lock(lockPath: Path, operation: str) -> Iterator[None]:
    pathLock = lockPath / _STR_LOCK_FILE_NAME
    strOwnerId = _create_lock(lockPath=pathLock, operation=operation)

    try:
        yield
    finally:
        _release_lock(lockPath=pathLock, ownerId=strOwnerId)
