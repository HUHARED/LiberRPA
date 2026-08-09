# FileName: _Lock.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import read_json, serialize_json
from liberrpa.ComponentManagement.Common._Validation import (
    validate_uuid_v4,
    validate_exact_keys,
    path_exists,
    is_file_invalid,
)
from liberrpa.ComponentManagement.Types._Lock import (
    DictComponentManagementLock_File,
)

from datetime import UTC, datetime
from pathlib import Path
import os
import time
import uuid
import psutil
from typing import Literal, cast


_FLOAT_INVALID_LOCK_GRACE_SECONDS = 5.0
_FLOAT_PROCESS_CREATE_TIME_TOLERANCE = 1.0

_SET_KEYS_LOCK_FILE = {
    "schemaVersion",
    "ownerId",
    "processId",
    "processCreateTime",
    "operation",
    "createdAt",
}


def _get_lock_owner_process_identity(value: object) -> tuple[int, float] | None:
    if not isinstance(value, dict):
        return None

    processId = value.get("processId")
    processCreateTime = value.get("processCreateTime")

    if type(processId) is not int or processId <= 0:
        return None
    if (
        isinstance(processCreateTime, bool)
        or not isinstance(processCreateTime, (int, float))
        or processCreateTime <= 0
    ):
        return None

    return processId, float(processCreateTime)


def _is_lock_owner_active(value: object) -> bool | None:
    processIdentity = _get_lock_owner_process_identity(value)
    if processIdentity is None:
        return None

    processId, processCreateTime = processIdentity

    try:
        processObj = psutil.Process(processId)
        return (
            abs(processObj.create_time() - processCreateTime)
            <= _FLOAT_PROCESS_CREATE_TIME_TOLERANCE
        )
    except psutil.NoSuchProcess:
        return False
    except (psutil.AccessDenied, psutil.ZombieProcess):
        return True


def _validate_lock_file(value: object) -> DictComponentManagementLock_File:
    if not isinstance(value, dict):
        raise ValueError("Lock file root value must be an object.")

    validate_exact_keys(value, _SET_KEYS_LOCK_FILE, "lock file")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("Lock file schemaVersion must be 1.")

    strOwnerId = validate_uuid_v4(value.get("ownerId"), "ownerId")

    processIdentity = _get_lock_owner_process_identity(value)
    if processIdentity is None:
        raise ValueError("processId and processCreateTime must identify a valid process.")
    processId, processCreateTime = processIdentity

    operation = value.get("operation")
    if (
        not isinstance(operation, str)
        or operation.strip() == ""
        or operation != operation.strip()
        or "\r" in operation
        or "\n" in operation
    ):
        raise ValueError("operation must be a trimmed non-empty single-line string.")

    createdAt = value.get("createdAt")
    if not isinstance(createdAt, str) or not createdAt.endswith("Z"):
        raise ValueError("createdAt must be a UTC ISO 8601 timestamp ending in 'Z'.")

    try:
        createdAtObj = datetime.fromisoformat(createdAt[:-1] + "+00:00")
    except ValueError as e:
        raise ValueError("createdAt must be a valid ISO 8601 timestamp.") from e

    if createdAtObj.isoformat().replace("+00:00", "Z") != createdAt:
        raise ValueError("createdAt must use the canonical UTC ISO 8601 form.")

    return cast(
        DictComponentManagementLock_File,
        {
            "schemaVersion": 1,
            "ownerId": strOwnerId,
            "processId": processId,
            "processCreateTime": processCreateTime,
            "operation": operation,
            "createdAt": createdAt,
        },
    )


def _get_lock_file_age_seconds(lockFilePath: Path) -> float | None:
    try:
        return time.time() - lockFilePath.lstat().st_mtime
    except OSError:
        return None


def _try_remove_stale_lock(lockFilePath: Path) -> bool:
    if is_file_invalid(lockFilePath):
        floatAge = _get_lock_file_age_seconds(lockFilePath)
        if floatAge is None or floatAge < _FLOAT_INVALID_LOCK_GRACE_SECONDS:
            return False

        if lockFilePath.is_symlink() or lockFilePath.is_file():
            lockFilePath.unlink(missing_ok=True)
            return True

        return False

    try:
        value = read_json(lockFilePath)
    except (OSError, ValueError):
        floatAge = _get_lock_file_age_seconds(lockFilePath)
        if floatAge is None or floatAge < _FLOAT_INVALID_LOCK_GRACE_SECONDS:
            return False

        lockFilePath.unlink(missing_ok=True)
        return True

    try:
        _validate_lock_file(value)
    except ValueError:
        boolCurrentSchemaValid = False
    else:
        boolCurrentSchemaValid = True

    boolOwnerActive = _is_lock_owner_active(value)
    if boolOwnerActive is True:
        # Preserve an active lock even when it was written by a newer schema that this LiberRPA version cannot fully validate.
        return False

    if not boolCurrentSchemaValid and boolOwnerActive is None:
        floatAge = _get_lock_file_age_seconds(lockFilePath)
        if floatAge is None or floatAge < _FLOAT_INVALID_LOCK_GRACE_SECONDS:
            return False

    lockFilePath.unlink(missing_ok=True)
    return True


def create_lock(
    lockFilePath: Path,
    operation: str,
    lockType: Literal["project", "repository"],
) -> str:
    strOwnerId = str(uuid.uuid4())
    dictLock: DictComponentManagementLock_File = {
        "schemaVersion": 1,
        "ownerId": strOwnerId,
        "processId": os.getpid(),
        "processCreateTime": float(psutil.Process().create_time()),
        "operation": operation,
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    bytesLock = (serialize_json(dictLock, compact=True) + "\n").encode()

    boolRetried = False

    while True:
        try:
            intFileDescriptor = os.open(
                lockFilePath,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            if not boolRetried and _try_remove_stale_lock(lockFilePath):
                boolRetried = True
                continue

            raise ComponentManagementError(
                code=f"{lockType}_busy",
                message=(
                    f"Another Component operation is currently modifying the {lockType}."
                ),
                details={"operationLockFilePath": str(lockFilePath)},
            )
        except OSError as e:
            raise ComponentManagementError(
                code=f"{lockType}_lock_failed",
                message=f"Failed to create the {lockType} lock.",
                details={
                    "operationLockFilePath": str(lockFilePath),
                    "reason": str(e),
                },
            ) from e

        try:
            with os.fdopen(intFileDescriptor, "wb", closefd=True) as fileObj:
                fileObj.write(bytesLock)
                fileObj.flush()
                os.fsync(fileObj.fileno())
        except OSError as e:
            try:
                lockFilePath.unlink(missing_ok=True)
            except OSError:
                pass

            raise ComponentManagementError(
                code=f"{lockType}_lock_failed",
                message=f"Failed to write the {lockType} lock.",
                details={
                    "operationLockFilePath": str(lockFilePath),
                    "reason": str(e),
                },
            ) from e

        return strOwnerId


def release_lock(lockFilePath: Path, ownerId: str) -> None:
    if not path_exists(lockFilePath) or is_file_invalid(lockFilePath):
        return

    try:
        dictLock = _validate_lock_file(read_json(lockFilePath))
    except (OSError, ValueError):
        return

    if dictLock["ownerId"] == ownerId:
        lockFilePath.unlink(missing_ok=True)
