# FileName: _ImportTransaction.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import read_json, write_json_atomic
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
    DictRepository_Transaction_ImportArtifact,
    DictRepository_Transaction_Import,
)
from liberrpa.ComponentManagement.Domain.Wheel._Wheel import inspect_component_wheel
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
from liberrpa.ComponentManagement.Domain.Repository._VersionEntry import (
    build_repository_version_entry,
)

from pathlib import Path, PurePosixPath
import os
from typing import cast


_SET_KEYS_TRANSACTION = {
    "schemaVersion",
    "operation",
    "state",
    "artifacts",
}
_SET_KEYS_ARTIFACT = {
    "artifactRelativePath",
    "componentId",
    "packageName",
    "versionEntry",
    "targetRelativePath",
}


def _validate_artifact(
    value: object,
    field: str,
) -> DictRepository_Transaction_ImportArtifact:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    validate_exact_keys(value, _SET_KEYS_ARTIFACT, field)

    artifactRelativePath = value.get("artifactRelativePath")
    if not isinstance(artifactRelativePath, str):
        raise ValueError(f"{field}.artifactRelativePath must be a string.")

    strComponentId = validate_component_id(
        value.get("componentId"), f"{field}.componentId"
    )

    packageName = value.get("packageName")
    if not isinstance(packageName, str):
        raise ValueError(f"{field}.packageName must be a string.")
    strPackageNameError = get_package_name_error(packageName)
    if strPackageNameError is not None:
        raise ValueError(f"{field}.packageName: {strPackageNameError}")

    dictVersionEntry = validate_repository_version(
        value.get("versionEntry"),
        f"{field}.versionEntry",
        componentId=strComponentId,
        packageName=packageName,
    )

    pathArtifactRelative = PurePosixPath(artifactRelativePath)
    if (
        pathArtifactRelative.as_posix() != artifactRelativePath
        or len(pathArtifactRelative.parts) != 2
        or not pathArtifactRelative.parts[0].isascii()
        or not pathArtifactRelative.parts[0].isdigit()
        or f"{int(pathArtifactRelative.parts[0]):04d}" != pathArtifactRelative.parts[0]
        or pathArtifactRelative.name != dictVersionEntry["wheelFileName"]
    ):
        raise ValueError(
            f"{field}.artifactRelativePath must use '<zero-padded source index>/<Wheel filename>'."
        )

    targetRelativePath = value.get("targetRelativePath")
    if not isinstance(targetRelativePath, str):
        raise ValueError(f"{field}.targetRelativePath must be a string.")

    strExpectedRelativePath = get_wheel_relative_path(
        componentId=strComponentId,
        packageName=packageName,
        wheelFileName=dictVersionEntry["wheelFileName"],
    )
    if targetRelativePath != strExpectedRelativePath:
        raise ValueError(
            f"{field}.targetRelativePath does not match the Component Wheel identity."
        )

    return cast(
        DictRepository_Transaction_ImportArtifact,
        {
            "artifactRelativePath": artifactRelativePath,
            "componentId": strComponentId,
            "packageName": packageName,
            "versionEntry": dictVersionEntry,
            "targetRelativePath": strExpectedRelativePath,
        },
    )


def _validate_transaction(value: object) -> DictRepository_Transaction_Import:
    if not isinstance(value, dict):
        raise ValueError("Transaction root value must be an object.")

    validate_exact_keys(value, _SET_KEYS_TRANSACTION, "transaction.json")

    schemaVersion = value.get("schemaVersion")
    if (
        type(schemaVersion) is not int
        or schemaVersion != 1
        or value.get("operation") != "importComponentWheels"
    ):
        raise ValueError("Unsupported Repository import transaction.")

    state = value.get("state")
    if state not in {"prepared", "wheelsCommitted"}:
        raise ValueError("Invalid Repository import transaction state.")

    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError(
            "Repository import transaction artifacts must be a non-empty array."
        )

    listArtifact = [
        _validate_artifact(artifactValue, f"artifacts[{intIndex}]")
        for intIndex, artifactValue in enumerate(artifacts)
    ]

    setArtifactPath: set[str] = set()
    setTargetPath: set[str] = set()
    for dictArtifact in listArtifact:
        strArtifactKey = dictArtifact["artifactRelativePath"].casefold()

        if strArtifactKey in setArtifactPath:
            raise ValueError(
                "Repository import transaction contains duplicate staged Wheel paths."
            )

        setArtifactPath.add(strArtifactKey)

        strTargetKey = dictArtifact["targetRelativePath"].casefold()
        if strTargetKey in setTargetPath:
            raise ValueError(
                "Repository import transaction contains duplicate target Wheel paths."
            )
        setTargetPath.add(strTargetKey)

    return {
        "schemaVersion": 1,
        "operation": "importComponentWheels",
        "state": state,
        "artifacts": listArtifact,
    }


def _collect_import_transactions(
    repositoryPath: Path,
    *,
    errorCode: Str_Repository_Error_Code,
) -> tuple[list[Path], list[tuple[Path, Path, DictRepository_Transaction_Import]]]:
    pathStagingFolder = get_repository_staging_folder_path(repositoryPath)
    if not path_exists(pathStagingFolder):
        return [], []

    if is_folder_invalid(pathStagingFolder):
        raise ComponentManagementError(
            code=errorCode,
            message=f"Component Repository staging path is invalid: {pathStagingFolder}",
        )

    listCleanupFolderPath: list[Path] = []
    listTransaction: list[tuple[Path, Path, DictRepository_Transaction_Import]] = []

    for pathTransactionFolder in sorted(
        pathStagingFolder.glob("import_*"), key=lambda pathObj: pathObj.name
    ):
        try:
            validate_repository_transaction_folder_name(
                pathTransactionFolder.name,
                "import",
            )
        except ValueError as e:
            raise ComponentManagementError(
                code=errorCode,
                message=(
                    "Component Repository staging contains an invalid import "
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
                message="Component Repository staging contains an invalid import transaction path.",
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
                message=f"Invalid Component Repository import transaction: {pathTransactionFile}",
                details={"reason": str(e)},
            ) from e

        listTransaction.append((
            pathTransactionFolder,
            pathTransactionFile,
            dictTransaction,
        ))

    return listCleanupFolderPath, listTransaction


def _validate_wheel_against_artifact(
    wheelFilePath: Path,
    artifactDict: DictRepository_Transaction_ImportArtifact,
    *,
    errorCode: Str_Repository_Error_Code,
) -> None:
    if is_file_invalid(wheelFilePath):
        raise ComponentManagementError(
            code=errorCode,
            message="An interrupted Repository import transaction contains an invalid Wheel path.",
            details={"wheelFilePath": str(wheelFilePath)},
        )

    try:
        wheelInfoObj = inspect_component_wheel(wheelFilePath)
    except ComponentManagementError as e:
        raise ComponentManagementError(
            code=errorCode,
            message=(
                "A Wheel from an interrupted Repository import transaction is invalid."
            ),
            details={
                "wheelFilePath": str(wheelFilePath),
                "reason": e.message,
            },
        ) from e

    manifestObj = wheelInfoObj.manifest
    dictActualVersionEntry = build_repository_version_entry(
        manifestObj=manifestObj,
        wheelFileName=wheelInfoObj.wheelFileName,
        sha256=wheelInfoObj.sha256,
    )
    if (
        manifestObj.id != artifactDict["componentId"]
        or manifestObj.packageName != artifactDict["packageName"]
        or manifestObj.version != artifactDict["versionEntry"]["version"]
        or wheelInfoObj.wheelFileName != artifactDict["versionEntry"]["wheelFileName"]
        or wheelInfoObj.sha256 != artifactDict["versionEntry"]["sha256"]
        or dictActualVersionEntry != artifactDict["versionEntry"]
    ):
        raise ComponentManagementError(
            code=errorCode,
            message="A Wheel identity does not match its interrupted Repository import transaction.",
            details={"wheelFilePath": str(wheelFilePath)},
        )


def _inspect_import_transaction_state(
    repositoryPath: Path,
    indexDict: DictRepository_Index,
    transactionFolderPath: Path,
    transactionFilePath: Path,
    transactionDict: DictRepository_Transaction_Import,
    *,
    errorCode: Str_Repository_Error_Code,
) -> list[
    tuple[
        DictRepository_Transaction_ImportArtifact,
        Path | None,
        Path | None,
        DictRepository_ComponentVersionEntry | None,
    ]
]:
    pathArtifactsFolder = transactionFolderPath / "artifacts"
    if is_folder_invalid(pathArtifactsFolder):
        raise ComponentManagementError(
            code=errorCode,
            message="An interrupted Repository import transaction has an invalid artifacts folder.",
            details={"transactionFilePath": str(transactionFilePath)},
        )

    listState: list[
        tuple[
            DictRepository_Transaction_ImportArtifact,
            Path | None,
            Path | None,
            DictRepository_ComponentVersionEntry | None,
        ]
    ] = []

    for dictArtifact in transactionDict["artifacts"]:
        pathStagedWheelFile = pathArtifactsFolder.joinpath(
            *PurePosixPath(dictArtifact["artifactRelativePath"]).parts
        )
        pathTargetWheelFile = repositoryPath.joinpath(
            *PurePosixPath(dictArtifact["targetRelativePath"]).parts
        )
        boolStagedExists = path_exists(pathStagedWheelFile)
        boolTargetExists = path_exists(pathTargetWheelFile)

        if boolStagedExists and boolTargetExists:
            raise ComponentManagementError(
                code=errorCode,
                message="An interrupted Repository import transaction has both staged and committed copies of a Wheel.",
                details={
                    "transactionFilePath": str(transactionFilePath),
                    "stagedWheelFilePath": str(pathStagedWheelFile),
                    "targetWheelFilePath": str(pathTargetWheelFile),
                },
            )

        if not boolStagedExists and not boolTargetExists:
            raise ComponentManagementError(
                code=errorCode,
                message="A Wheel is missing from an interrupted Repository import transaction.",
                details={
                    "transactionFilePath": str(transactionFilePath),
                    "wheelFileName": dictArtifact["versionEntry"]["wheelFileName"],
                },
            )

        if transactionDict["state"] == "wheelsCommitted" and not boolTargetExists:
            raise ComponentManagementError(
                code=errorCode,
                message="An interrupted Repository import transaction recorded all Wheels as committed, but a target Wheel is missing.",
                details={
                    "transactionFilePath": str(transactionFilePath),
                    "wheelFilePath": str(pathTargetWheelFile),
                },
            )

        if boolStagedExists:
            _validate_wheel_against_artifact(
                pathStagedWheelFile, dictArtifact, errorCode=errorCode
            )
        if boolTargetExists:
            _validate_wheel_against_artifact(
                pathTargetWheelFile, dictArtifact, errorCode=errorCode
            )

        dictComponent = indexDict["components"].get(dictArtifact["componentId"])
        if (
            dictComponent is not None
            and dictComponent["packageName"] != dictArtifact["packageName"]
        ):
            raise ComponentManagementError(
                code=errorCode,
                message=(
                    "The Repository index binds an interrupted import "
                    "artifact's Component ID to a different packageName."
                ),
                details={
                    "transactionFilePath": str(transactionFilePath),
                    "componentId": dictArtifact["componentId"],
                    "indexedPackageName": dictComponent["packageName"],
                    "transactionPackageName": dictArtifact["packageName"],
                },
            )

        dictExistingVersionEntry = (
            None
            if dictComponent is None
            else find_equivalent_version(
                dictComponent, dictArtifact["versionEntry"]["version"]
            )
        )
        if dictExistingVersionEntry is not None:
            if dictExistingVersionEntry != dictArtifact["versionEntry"]:
                raise ComponentManagementError(
                    code=errorCode,
                    message="The Repository index conflicts with an interrupted import transaction.",
                    details={"transactionFilePath": str(transactionFilePath)},
                )
            if not boolTargetExists:
                raise ComponentManagementError(
                    code=errorCode,
                    message="The Repository index references a Wheel that is still only in import staging.",
                    details={"transactionFilePath": str(transactionFilePath)},
                )

        listState.append((
            dictArtifact,
            pathStagedWheelFile if boolStagedExists else None,
            pathTargetWheelFile if boolTargetExists else None,
            dictExistingVersionEntry,
        ))

    return listState


def recover_import_transactions(
    repositoryPath: Path,
) -> list[DictComponentManagementWarning]:
    listTransactionCleanup, listTransaction = _collect_import_transactions(
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
        listState = _inspect_import_transaction_state(
            repositoryPath,
            dictIndex,
            pathTransactionFolder,
            pathTransactionFile,
            dictTransaction,
            errorCode="repository_recovery_failed",
        )

        try:
            for dictArtifact, pathStagedWheelFile, pathTargetWheelFile, _ in listState:
                if pathTargetWheelFile is None:
                    assert pathStagedWheelFile is not None
                    pathTargetWheelFile = repositoryPath.joinpath(
                        *PurePosixPath(dictArtifact["targetRelativePath"]).parts
                    )
                    pathTargetWheelFile.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(pathStagedWheelFile, pathTargetWheelFile)

            dictTransaction["state"] = "wheelsCommitted"
            write_json_atomic(pathTransactionFile, dictTransaction)

            for dictArtifact, _, _, dictExistingVersionEntry in listState:
                if dictExistingVersionEntry is None:
                    add_version_to_index(
                        indexDict=dictIndex,
                        componentId=dictArtifact["componentId"],
                        packageName=dictArtifact["packageName"],
                        versionEntry=dictArtifact["versionEntry"],
                    )

            write_repository_index(repositoryPath, dictIndex)
        except ComponentManagementError:
            raise
        except OSError as e:
            raise ComponentManagementError(
                code="repository_recovery_failed",
                message="Failed to finish an interrupted Component Repository import transaction.",
                details={"transactionFilePath": str(pathTransactionFile)},
            ) from e

        dictWarning = remove_repository_transaction_folder(pathTransactionFolder)
        if dictWarning is not None:
            listWarning.append(dictWarning)

    return listWarning


def validate_import_transactions_for_rebuild(
    repositoryPath: Path,
    indexDict: DictRepository_Index,
) -> list[Path]:
    listCleanupFolderPath, listTransaction = _collect_import_transactions(
        repositoryPath,
        errorCode="repository_rebuild_failed",
    )

    for pathTransactionFolder, pathTransactionFile, dictTransaction in listTransaction:
        listState = _inspect_import_transaction_state(
            repositoryPath,
            indexDict,
            pathTransactionFolder,
            pathTransactionFile,
            dictTransaction,
            errorCode="repository_rebuild_failed",
        )

        try:
            for (
                dictArtifact,
                pathStagedWheelFile,
                pathTargetWheelFile,
                dictExistingVersionEntry,
            ) in listState:
                if pathTargetWheelFile is None:
                    assert pathStagedWheelFile is not None
                    pathTargetWheelFile = repositoryPath.joinpath(
                        *PurePosixPath(dictArtifact["targetRelativePath"]).parts
                    )
                    pathTargetWheelFile.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(pathStagedWheelFile, pathTargetWheelFile)

                if dictExistingVersionEntry is None:
                    add_version_to_index(
                        indexDict=indexDict,
                        componentId=dictArtifact["componentId"],
                        packageName=dictArtifact["packageName"],
                        versionEntry=dictArtifact["versionEntry"],
                    )

            dictTransaction["state"] = "wheelsCommitted"
            write_json_atomic(pathTransactionFile, dictTransaction)
        except ComponentManagementError:
            raise
        except OSError as e:
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message="Failed to finish an interrupted Component Repository import transaction during rebuild.",
                details={"transactionFilePath": str(pathTransactionFile)},
            ) from e

        listCleanupFolderPath.append(pathTransactionFolder)

    return listCleanupFolderPath
