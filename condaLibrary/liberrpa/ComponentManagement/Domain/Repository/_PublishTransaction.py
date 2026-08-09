# FileName: _PublishTransaction.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import read_json
from liberrpa.ComponentManagement.Common._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Common._Validation import (
    get_package_name_error,
    validate_exact_keys,
    path_exists,
    is_file_invalid,
    is_folder_invalid,
)
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Repository import (
    Str_Repository_Error_Code,
    DictRepository_ComponentVersionEntry,
    DictRepository_Index,
    DictRepository_Transaction_Publish,
)
from liberrpa.ComponentManagement.Domain.Repository._Index import (
    validate_component_id,
    validate_repository_version,
    get_wheel_relative_path,
    load_repository_index,
    write_repository_index,
    find_equivalent_version,
    add_version_to_index,
)
from liberrpa.ComponentManagement.Domain.Repository._TransactionStorage import (
    get_repository_staging_folder_path,
    validate_repository_transaction_folder_name,
    remove_repository_transaction_folder,
)

from pathlib import Path, PurePosixPath
from typing import cast


_SET_KEYS_TRANSACTION = {
    "schemaVersion",
    "operation",
    "state",
    "componentId",
    "packageName",
    "versionEntry",
    "targetRelativePath",
}


def _validate_transaction(value: object) -> DictRepository_Transaction_Publish:
    if not isinstance(value, dict):
        raise ValueError("Transaction root value must be an object.")

    validate_exact_keys(value, _SET_KEYS_TRANSACTION, "transaction.json")

    schemaVersion = value.get("schemaVersion")
    if (
        type(schemaVersion) is not int
        or schemaVersion != 1
        or value.get("operation") != "publishComponent"
    ):
        raise ValueError("Unsupported Repository transaction.")

    state = value.get("state")
    if state not in {"prepared", "wheelCommitted"}:
        raise ValueError("Invalid Repository transaction state.")

    strComponentId = validate_component_id(value.get("componentId"), "componentId")

    packageName = value.get("packageName")
    if not isinstance(packageName, str):
        raise ValueError("packageName must be a string.")
    strPackageNameError = get_package_name_error(packageName)
    if strPackageNameError is not None:
        raise ValueError(f"packageName: {strPackageNameError}")

    dictVersionEntry = validate_repository_version(
        value.get("versionEntry"),
        "versionEntry",
        componentId=strComponentId,
        packageName=packageName,
    )

    targetRelativePath = value.get("targetRelativePath")
    if not isinstance(targetRelativePath, str):
        raise ValueError("targetRelativePath must be a string.")

    strExpectedRelativePath = get_wheel_relative_path(
        componentId=strComponentId,
        packageName=packageName,
        wheelFileName=dictVersionEntry["wheelFileName"],
    )
    if targetRelativePath != strExpectedRelativePath:
        raise ValueError("targetRelativePath does not match the Component identity.")

    return cast(
        DictRepository_Transaction_Publish,
        {
            "schemaVersion": 1,
            "operation": "publishComponent",
            "state": state,
            "componentId": strComponentId,
            "packageName": packageName,
            "versionEntry": dictVersionEntry,
            "targetRelativePath": targetRelativePath,
        },
    )


def _collect_publish_transactions(
    repositoryPath: Path,
    *,
    errorCode: Str_Repository_Error_Code,
) -> tuple[list[Path], list[tuple[Path, Path, DictRepository_Transaction_Publish]]]:
    pathStagingFolder = get_repository_staging_folder_path(repositoryPath)
    if not path_exists(pathStagingFolder):
        return [], []

    if is_folder_invalid(pathStagingFolder):
        raise ComponentManagementError(
            code=errorCode,
            message=f"Component Repository staging path is invalid: {pathStagingFolder}",
        )

    listCleanupFolderPath: list[Path] = []
    listTransaction: list[tuple[Path, Path, DictRepository_Transaction_Publish]] = []

    for pathTransactionFolder in sorted(
        pathStagingFolder.glob("publish_*"), key=lambda pathObj: pathObj.name
    ):
        try:
            validate_repository_transaction_folder_name(
                pathTransactionFolder.name,
                "publish",
            )
        except ValueError as e:
            raise ComponentManagementError(
                code=errorCode,
                message=(
                    "Component Repository staging contains an invalid publish "
                    "transaction folder name."
                ),
                details={
                    "transactionFolderPath": str(pathTransactionFolder),
                    "reason": str(e),
                },
            ) from e

        if is_folder_invalid(pathTransactionFolder):
            raise ComponentManagementError(
                code=errorCode,
                message="Component Repository staging contains an invalid publish transaction path.",
                details={"transactionFolderPath": str(pathTransactionFolder)},
            )

        pathTransactionFile = pathTransactionFolder / "transaction.json"
        if is_file_invalid(pathTransactionFile):
            listCleanupFolderPath.append(pathTransactionFolder)
            continue

        try:
            dictTransaction = _validate_transaction(read_json(pathTransactionFile))
        except (OSError, ValueError) as e:
            raise ComponentManagementError(
                code=errorCode,
                message=f"Invalid Component Repository transaction: {pathTransactionFile}",
                details={"reason": str(e)},
            ) from e

        listTransaction.append((
            pathTransactionFolder,
            pathTransactionFile,
            dictTransaction,
        ))

    return listCleanupFolderPath, listTransaction


def _inspect_publish_transaction_state(
    repositoryPath: Path,
    indexDict: DictRepository_Index,
    transactionFilePath: Path,
    transactionDict: DictRepository_Transaction_Publish,
    *,
    errorCode: Str_Repository_Error_Code,
) -> tuple[Path, DictRepository_ComponentVersionEntry | None]:
    pathTargetWheelFile = repositoryPath.joinpath(
        *PurePosixPath(transactionDict["targetRelativePath"]).parts
    )
    dictComponent = indexDict["components"].get(transactionDict["componentId"])
    if (
        dictComponent is not None
        and dictComponent["packageName"] != transactionDict["packageName"]
    ):
        raise ComponentManagementError(
            code=errorCode,
            message=(
                "The Repository index binds the interrupted transaction's "
                "Component ID to a different packageName."
            ),
            details={
                "transactionFilePath": str(transactionFilePath),
                "componentId": transactionDict["componentId"],
                "indexedPackageName": dictComponent["packageName"],
                "transactionPackageName": transactionDict["packageName"],
            },
        )

    dictExistingVersionEntry = (
        None
        if dictComponent is None
        else find_equivalent_version(
            dictComponent, transactionDict["versionEntry"]["version"]
        )
    )

    if pathTargetWheelFile.is_symlink() or (
        pathTargetWheelFile.exists() and not pathTargetWheelFile.is_file()
    ):
        raise ComponentManagementError(
            code=errorCode,
            message="The target path of an interrupted Repository transaction is not a Wheel file.",
            details={
                "transactionFilePath": str(transactionFilePath),
                "wheelFilePath": str(pathTargetWheelFile),
            },
        )

    if pathTargetWheelFile.is_file():
        try:
            strActualSha256 = calculate_file_sha256(pathTargetWheelFile)
        except OSError as e:
            raise ComponentManagementError(
                code=errorCode,
                message="Failed to read a committed Wheel from an interrupted Repository transaction.",
                details={"wheelFilePath": str(pathTargetWheelFile), "reason": str(e)},
            ) from e

        if strActualSha256 != transactionDict["versionEntry"]["sha256"]:
            raise ComponentManagementError(
                code=errorCode,
                message="A committed Component Wheel does not match its interrupted transaction.",
                details={
                    "wheelFilePath": str(pathTargetWheelFile),
                    "expectedSha256": transactionDict["versionEntry"]["sha256"],
                    "actualSha256": strActualSha256,
                },
            )
    else:
        if dictExistingVersionEntry is not None:
            raise ComponentManagementError(
                code=errorCode,
                message="The Repository index references a Wheel missing from an interrupted transaction.",
                details={"wheelFilePath": str(pathTargetWheelFile)},
            )

        if transactionDict["state"] == "wheelCommitted":
            raise ComponentManagementError(
                code=errorCode,
                message=(
                    "An interrupted Repository transaction recorded the Wheel as committed, but the target Wheel is missing."
                ),
                details={
                    "transactionFilePath": str(transactionFilePath),
                    "wheelFilePath": str(pathTargetWheelFile),
                },
            )

    return pathTargetWheelFile, dictExistingVersionEntry


def recover_publish_transactions(
    repositoryPath: Path,
) -> list[DictComponentManagementWarning]:
    listTransactionCleanup, listTransaction = _collect_publish_transactions(
        repositoryPath,
        errorCode="repository_recovery_failed",
    )
    if not listTransactionCleanup and not listTransaction:
        return []

    listWarning: list[DictComponentManagementWarning] = []
    for pathTransactionFolder in listTransactionCleanup:
        dictWarning = remove_repository_transaction_folder(pathTransactionFolder)
        if dictWarning is not None:
            listWarning.append(dictWarning)

    dictIndex = load_repository_index(repositoryPath, checkWheelFilePaths=False)

    for pathTransactionFolder, pathTransactionFile, dictTransaction in listTransaction:
        pathTargetWheelFile, dictExistingVersionEntry = (
            _inspect_publish_transaction_state(
                repositoryPath,
                dictIndex,
                pathTransactionFile,
                dictTransaction,
                errorCode="repository_recovery_failed",
            )
        )

        if pathTargetWheelFile.is_file():
            if dictExistingVersionEntry is None:
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
                        details={"transactionFilePath": str(pathTransactionFile)},
                    ) from e
                except OSError as e:
                    raise ComponentManagementError(
                        code="repository_recovery_failed",
                        message="Failed to finish an interrupted Component Repository publish transaction.",
                    ) from e
            elif dictExistingVersionEntry != dictTransaction["versionEntry"]:
                # Dictionary equality compares every version-entry field and is more comprehensive than comparing only SHA-256.
                raise ComponentManagementError(
                    code="repository_recovery_failed",
                    message="The Repository index conflicts with an interrupted publish transaction.",
                    details={"transactionFilePath": str(pathTransactionFile)},
                )

        # prepared + no target Wheel + no index entry means nothing entered the formal Repository, so the transaction can be removed.
        dictWarning = remove_repository_transaction_folder(pathTransactionFolder)
        if dictWarning is not None:
            listWarning.append(dictWarning)

    return listWarning


def validate_publish_transactions_for_rebuild(
    repositoryPath: Path,
    indexDict: DictRepository_Index,
) -> list[Path]:
    listCleanupFolderPath, listTransaction = _collect_publish_transactions(
        repositoryPath,
        errorCode="repository_rebuild_failed",
    )

    for pathTransactionFolder, pathTransactionFile, dictTransaction in listTransaction:
        pathTargetWheelFile, dictExistingVersionEntry = (
            _inspect_publish_transaction_state(
                repositoryPath,
                indexDict,
                pathTransactionFile,
                dictTransaction,
                errorCode="repository_rebuild_failed",
            )
        )

        if (
            pathTargetWheelFile.is_file()
            and dictExistingVersionEntry != dictTransaction["versionEntry"]
        ):
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message="The rebuilt Repository index conflicts with an interrupted publish transaction.",
                details={"transactionFilePath": str(pathTransactionFile)},
            )

        listCleanupFolderPath.append(pathTransactionFolder)

    return listCleanupFolderPath
