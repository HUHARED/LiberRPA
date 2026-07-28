# FileName: _RepositoryTransaction.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import read_json
from liberrpa.ComponentManagement.Utils._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Utils._TypedValue import (
    DictComponentManagementWarning,
    DictRepositoryIndex,
    DictRepositoryTransaction,
)
from liberrpa.ComponentManagement.Utils._Version import normalize_version
from liberrpa.ComponentManagement.Utils._Validation import get_package_name_error
from liberrpa.ComponentManagement._RepositoryIndex import (
    validate_exact_keys,
    normalize_component_id,
    validate_repository_version,
    get_wheel_relative_path,
    load_repository_index,
    write_repository_index,
    find_equivalent_version,
    add_version_to_index,
)

from pathlib import Path, PurePosixPath
import os
import shutil
from typing import cast

_STR_STAGING_FOLDER_NAME = ".staging"

_SET_TRANSACTION_KEYS = {
    "schemaVersion",
    "operation",
    "state",
    "componentId",
    "packageName",
    "version",
    "wheelFile",
    "sha256",
    "targetRelativePath",
    "versionEntry",
}


def _validate_transaction(value: object) -> DictRepositoryTransaction:
    if not isinstance(value, dict):
        raise ValueError("Transaction root value must be an object.")

    validate_exact_keys(value, _SET_TRANSACTION_KEYS, "transaction.json")

    if value.get("schemaVersion") != 1 or value.get("operation") != "publishComponent":
        raise ValueError("Unsupported Repository transaction.")

    state = value.get("state")
    if state not in {"prepared", "wheelCommitted"}:
        raise ValueError("Invalid Repository transaction state.")

    strComponentId = normalize_component_id(value.get("componentId"), "componentId")

    packageName = value.get("packageName")
    if not isinstance(packageName, str):
        raise ValueError("packageName must be a string.")
    strPackageNameError = get_package_name_error(packageName)
    if strPackageNameError is not None:
        raise ValueError(f"packageName: {strPackageNameError}")

    version = value.get("version")
    if not isinstance(version, str) or normalize_version(version) != version:
        raise ValueError("version must use the normalized PEP 440 form.")

    dictVersionEntry = validate_repository_version(
        value.get("versionEntry"),
        "versionEntry",
        componentId=strComponentId,
        packageName=packageName,
    )

    wheelFile = value.get("wheelFile")
    sha256 = value.get("sha256")
    if wheelFile != dictVersionEntry["wheelFile"]:
        raise ValueError("wheelFile does not match versionEntry.")
    if sha256 != dictVersionEntry["sha256"]:
        raise ValueError("sha256 does not match versionEntry.")
    if version != dictVersionEntry["version"]:
        raise ValueError("version does not match versionEntry.")

    targetRelativePath = value.get("targetRelativePath")
    if not isinstance(targetRelativePath, str):
        raise ValueError("targetRelativePath must be a string.")

    strExpectedRelativePath = get_wheel_relative_path(
        componentId=strComponentId,
        packageName=packageName,
        wheelFile=dictVersionEntry["wheelFile"],
    )
    if targetRelativePath != strExpectedRelativePath:
        raise ValueError("targetRelativePath does not match the Component identity.")

    return cast(
        DictRepositoryTransaction,
        {
            "schemaVersion": 1,
            "operation": "publishComponent",
            "state": state,
            "componentId": strComponentId,
            "packageName": packageName,
            "version": version,
            "wheelFile": dictVersionEntry["wheelFile"],
            "sha256": dictVersionEntry["sha256"],
            "targetRelativePath": targetRelativePath,
            "versionEntry": dictVersionEntry,
        },
    )


def remove_transaction_folder(transactionPath: Path) -> DictComponentManagementWarning | None:
    try:
        shutil.rmtree(transactionPath)
    except OSError as e:
        return {
            "code": "repository_cleanup_pending",
            "message": f"Repository transaction recovery completed, but temporary files could not be removed: {transactionPath}",
            "details": {"reason": str(e)},
        }

    return None


def get_repository_staging_path(repositoryPath: Path) -> Path:
    return repositoryPath / _STR_STAGING_FOLDER_NAME


def recover_publish_transactions(repositoryPath: Path) -> list[DictComponentManagementWarning]:
    pathStaging = get_repository_staging_path(repositoryPath)
    if not pathStaging.exists():
        return []

    if not pathStaging.is_dir():
        raise ComponentManagementError(
            code="repository_recovery_failed",
            message=f"Component Repository staging path is invalid: {pathStaging}",
        )

    listWarning: list[DictComponentManagementWarning] = []
    dictIndex = load_repository_index(repositoryPath, checkWheelPaths=False)

    for pathTransaction in sorted(pathStaging.glob("publish_*"), key=lambda pathObj: pathObj.name):
        if not pathTransaction.is_dir():
            continue

        pathTransactionFile = pathTransaction / "transaction.json"
        if not pathTransactionFile.is_file():
            dictWarning = remove_transaction_folder(pathTransaction)
            if dictWarning is not None:
                listWarning.append(dictWarning)
            continue

        try:
            dictTransaction = _validate_transaction(read_json(pathTransactionFile))
        except (OSError, ValueError) as e:
            raise ComponentManagementError(
                code="repository_recovery_failed",
                message=f"Invalid Component Repository transaction: {pathTransactionFile}",
                details={"reason": str(e)},
            ) from e

        pathTargetWheel = repositoryPath.joinpath(*PurePosixPath(dictTransaction["targetRelativePath"]).parts)
        dictComponent = dictIndex["components"].get(dictTransaction["componentId"])
        dictExistingVersion = (
            None if dictComponent is None else find_equivalent_version(dictComponent, dictTransaction["version"])
        )

        if pathTargetWheel.exists() and not pathTargetWheel.is_file():
            raise ComponentManagementError(
                code="repository_recovery_failed",
                message="The target path of an interrupted Repository transaction is not a Wheel file.",
                details={
                    "transactionFile": str(pathTransactionFile),
                    "wheelFile": str(pathTargetWheel),
                },
            )

        if pathTargetWheel.is_file():
            strActualSha256 = calculate_file_sha256(pathTargetWheel)
            if strActualSha256 != dictTransaction["sha256"]:
                raise ComponentManagementError(
                    code="repository_recovery_failed",
                    message="A committed Component Wheel does not match its interrupted transaction.",
                    details={
                        "wheelFile": str(pathTargetWheel),
                        "expectedSha256": dictTransaction["sha256"],
                        "actualSha256": strActualSha256,
                    },
                )

            if dictExistingVersion is None:
                try:
                    add_version_to_index(
                        indexDict=dictIndex,
                        componentId=dictTransaction["componentId"],
                        packageName=dictTransaction["packageName"],
                        versionEntry=dictTransaction["versionEntry"],
                    )
                    write_repository_index(repositoryPath, dictIndex)
                except ComponentManagementError as e:
                    raise ComponentManagementError(
                        code="repository_recovery_failed",
                        message="The Repository index conflicts with an interrupted publish transaction.",
                        details={"transactionFile": str(pathTransactionFile)},
                    ) from e
                except OSError as e:
                    raise ComponentManagementError(
                        code="repository_recovery_failed",
                        message="Failed to finish an interrupted Component Repository publish transaction.",
                    ) from e
            elif dictExistingVersion != dictTransaction["versionEntry"]:
                # Dict objects will compare each item when using ==. It's more comprehensive and accurate than comparing SHA.
                raise ComponentManagementError(
                    code="repository_recovery_failed",
                    message="The Repository index conflicts with an interrupted publish transaction.",
                    details={"transactionFile": str(pathTransactionFile)},
                )
        else:
            if dictExistingVersion is not None:
                raise ComponentManagementError(
                    code="repository_recovery_failed",
                    message=("The Repository index references a Wheel missing from an interrupted transaction."),
                    details={"wheelFile": str(pathTargetWheel)},
                )

            if dictTransaction["state"] == "wheelCommitted":
                raise ComponentManagementError(
                    code="repository_recovery_failed",
                    message=(
                        "An interrupted Repository transaction recorded the Wheel as committed, but the target Wheel is missing."
                    ),
                    details={
                        "transactionFile": str(pathTransactionFile),
                        "wheelFile": str(pathTargetWheel),
                    },
                )

        # prepared + no target Wheel + no index entry means nothing entered the formal Repository, so the transaction can be removed.
        dictWarning = remove_transaction_folder(pathTransaction)
        if dictWarning is not None:
            listWarning.append(dictWarning)

    return listWarning


def copy_wheel_to_staging(sourcePath: Path, targetPath: Path) -> None:
    try:
        with sourcePath.open("rb") as sourceFileObj, targetPath.open("xb") as targetFileObj:
            shutil.copyfileobj(sourceFileObj, targetFileObj, length=1024 * 1024)
            targetFileObj.flush()
            os.fsync(targetFileObj.fileno())
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=(f"Failed to copy the Component Wheel into Repository staging: {targetPath}"),
        ) from e


def validate_publish_transactions_for_rebuild(
    repositoryPath: Path,
    indexDict: DictRepositoryIndex,
) -> list[Path]:
    pathStaging = get_repository_staging_path(repositoryPath)
    if not pathStaging.exists():
        return []

    if not pathStaging.is_dir() or pathStaging.is_symlink():
        raise ComponentManagementError(
            code="repository_rebuild_failed",
            message=f"Component Repository staging path is invalid: {pathStaging}",
        )

    listCleanupPath: list[Path] = []

    for pathTransaction in sorted(pathStaging.glob("publish_*"), key=lambda pathObj: pathObj.name):
        if not pathTransaction.is_dir() or pathTransaction.is_symlink():
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message="Component Repository staging contains an invalid publish transaction path.",
                details={"transactionPath": str(pathTransaction)},
            )

        pathTransactionFile = pathTransaction / "transaction.json"
        if not pathTransactionFile.is_file() or pathTransactionFile.is_symlink():
            listCleanupPath.append(pathTransaction)
            continue

        try:
            dictTransaction = _validate_transaction(read_json(pathTransactionFile))
        except (OSError, ValueError) as e:
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message=f"Invalid Component Repository transaction: {pathTransactionFile}",
                details={"reason": str(e)},
            ) from e

        pathTargetWheel = repositoryPath.joinpath(*PurePosixPath(dictTransaction["targetRelativePath"]).parts)
        dictComponent = indexDict["components"].get(dictTransaction["componentId"])
        dictExistingVersion = (
            None if dictComponent is None else find_equivalent_version(dictComponent, dictTransaction["version"])
        )

        if pathTargetWheel.exists() and not pathTargetWheel.is_file():
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message=("The target path of an interrupted Repository transaction is not a Wheel file."),
                details={
                    "transactionFile": str(pathTransactionFile),
                    "wheelFile": str(pathTargetWheel),
                },
            )

        if pathTargetWheel.is_file():
            strActualSha256 = calculate_file_sha256(pathTargetWheel)
            if strActualSha256 != dictTransaction["sha256"]:
                raise ComponentManagementError(
                    code="repository_rebuild_failed",
                    message=("A committed Component Wheel does not match its interrupted transaction."),
                    details={
                        "wheelFile": str(pathTargetWheel),
                        "expectedSha256": dictTransaction["sha256"],
                        "actualSha256": strActualSha256,
                    },
                )

            if dictExistingVersion != dictTransaction["versionEntry"]:
                raise ComponentManagementError(
                    code="repository_rebuild_failed",
                    message=("The rebuilt Repository index conflicts with an interrupted publish transaction."),
                    details={"transactionFile": str(pathTransactionFile)},
                )
        else:
            if dictExistingVersion is not None:
                raise ComponentManagementError(
                    code="repository_rebuild_failed",
                    message=(
                        "The rebuilt Repository index references a Wheel missing from an interrupted transaction."
                    ),
                    details={"wheelFile": str(pathTargetWheel)},
                )

            if dictTransaction["state"] == "wheelCommitted":
                raise ComponentManagementError(
                    code="repository_rebuild_failed",
                    message=(
                        "An interrupted Repository transaction recorded the Wheel "
                        "as committed, but the target Wheel is missing."
                    ),
                    details={
                        "transactionFile": str(pathTransactionFile),
                        "wheelFile": str(pathTargetWheel),
                    },
                )

        listCleanupPath.append(pathTransaction)

    return listCleanupPath
