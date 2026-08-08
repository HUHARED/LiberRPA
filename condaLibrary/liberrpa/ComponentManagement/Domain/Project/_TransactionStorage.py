# FileName: _TransactionStorage.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import read_json, write_json_atomic
from liberrpa.ComponentManagement.Common._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Common._Validation import (
    validate_exact_keys,
    path_exists,
    is_file_invalid,
    is_folder_invalid,
)
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Manifest import (
    Str_ProjectType,
    Str_ManifestFileName,
    Info_ProjectManifest,
)
from liberrpa.ComponentManagement.Types._Components import (
    DictComponentsLock_File,
    Info_ProjectComponentsFolder,
)
from liberrpa.ComponentManagement.Types._ProjectTransaction import (
    Str_ProjectTransaction_State,
    DictProjectTransaction_Snapshot,
    DictProjectTransaction,
)
from liberrpa.ComponentManagement.Domain.Project._Components import (
    STR_COMPONENTS_FOLDER_NAME,
    validate_components_folder,
    build_components_folder,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    write_components_lock,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import (
    build_project_manifest_dict,
    read_project_manifest,
)
from liberrpa.ComponentManagement.Domain.Repository._Index import validate_sha256

from pathlib import Path
from shutil import copyfileobj, rmtree
from typing import Literal
import os
import uuid


"""
Project dependency changes and _Components repairs use a same-volume transaction inside the Project:

<Project>/.liberrpa-project-manager/
└── transactions/
    └── project_<Transaction UUID>/
        ├── transaction.json
        ├── target/
        │   ├── flow.json or component.json
        │   ├── components.lock.json       # Optional.
        │   └── _Components/               # Optional.
        └── backup/
            ├── flow.json or component.json
            ├── components.lock.json       # Present only after the source file is moved.
            └── _Components/               # Present only after the source folder is moved.

_Components is committed first, components.lock.json second, and the Project Manifest last.
The Manifest replacement is the final commit step. If the source and target Manifest bytes are identical, an interrupted commit is conservatively rolled back unless transaction.json already records state "manifestCommitted".
"""


_STR_INTERNAL_FOLDER_NAME = ".liberrpa-project-manager"
_STR_TRANSACTIONS_FOLDER_NAME = "transactions"
_STR_TRANSACTION_FILE_NAME = "transaction.json"
STR_TARGET_FOLDER_NAME = "target"
STR_BACKUP_FOLDER_NAME = "backup"
STR_PROJECT_TRANSACTION_PREFIX = "project_"
_STR_PROJECT_TRANSACTION_TEMP_PREFIX = ".project_"
_STR_PROJECT_TRANSACTION_TEMP_SUFFIX = ".tmp"

_SET_TRANSACTION_KEYS_BASE = {
    "schemaVersion",
    "operation",
    "state",
    "projectType",
    "manifestFileName",
    "source",
    "target",
}
_SET_TRANSACTION_KEYS_APPLY = _SET_TRANSACTION_KEYS_BASE | {"planSha256"}
_SET_TRANSACTION_KEYS_REPAIR = set(_SET_TRANSACTION_KEYS_BASE)
_SET_KEYS_SNAPSHOT_BASE = {
    "manifestSha256",
    "componentsLockFileShouldExist",
    "componentsFolderShouldExist",
}


def get_transactions_path(projectPath: Path) -> Path:
    return projectPath / _STR_INTERNAL_FOLDER_NAME / _STR_TRANSACTIONS_FOLDER_NAME


def get_manifest_file_name(
    projectType: Str_ProjectType,
) -> Str_ManifestFileName:
    return "flow.json" if projectType == "flow" else "component.json"


def _validate_snapshot(
    value: object,
    field: str,
    *,
    isTarget: bool,
) -> DictProjectTransaction_Snapshot:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    boolComponentsLockFileShouldExist = value.get("componentsLockFileShouldExist")
    if type(boolComponentsLockFileShouldExist) is not bool:
        raise ValueError(f"{field}.componentsLockFileShouldExist must be a boolean.")

    setExpectedKey = set(_SET_KEYS_SNAPSHOT_BASE)
    if boolComponentsLockFileShouldExist:
        setExpectedKey.add("expectedComponentsLockFileSha256")
    validate_exact_keys(value, setExpectedKey, field)

    strManifestSha256 = validate_sha256(
        value.get("manifestSha256"), f"{field}.manifestSha256"
    )

    boolComponentsFolderShouldExist = value.get("componentsFolderShouldExist")
    if type(boolComponentsFolderShouldExist) is not bool:
        raise ValueError(f"{field}.componentsFolderShouldExist must be a boolean.")

    if isTarget and boolComponentsLockFileShouldExist != boolComponentsFolderShouldExist:
        raise ValueError(
            f"{field}.componentsLockFileShouldExist and {field}.componentsFolderShouldExist must have the same value."
        )

    dictSnapshot: DictProjectTransaction_Snapshot = {
        "manifestSha256": strManifestSha256,
        "componentsLockFileShouldExist": boolComponentsLockFileShouldExist,
        "componentsFolderShouldExist": boolComponentsFolderShouldExist,
    }

    if boolComponentsLockFileShouldExist:
        dictSnapshot["expectedComponentsLockFileSha256"] = validate_sha256(
            value.get("expectedComponentsLockFileSha256"),
            f"{field}.expectedComponentsLockFileSha256",
        )

    return dictSnapshot


def _validate_project_transaction(value: object) -> DictProjectTransaction:
    if not isinstance(value, dict):
        raise ValueError("Project transaction root value must be an object.")

    operationValue = value.get("operation")
    if operationValue == "applyDependencyPlan":
        validate_exact_keys(value, _SET_TRANSACTION_KEYS_APPLY, "transaction.json")
        strPlanSha256 = validate_sha256(value.get("planSha256"), "planSha256")
    elif operationValue == "repairProjectComponents":
        validate_exact_keys(value, _SET_TRANSACTION_KEYS_REPAIR, "transaction.json")
        strPlanSha256 = None
    else:
        raise ValueError("transaction.json contains an unsupported operation.")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("transaction.json schemaVersion must be 1.")

    transactionStateValue = value.get("state")
    if transactionStateValue == "prepared":
        transactionState: Str_ProjectTransaction_State = "prepared"
    elif transactionStateValue == "committing":
        transactionState = "committing"
    elif transactionStateValue == "manifestCommitted":
        transactionState = "manifestCommitted"
    else:
        raise ValueError("transaction.json contains an unsupported state.")

    projectTypeValue = value.get("projectType")
    if projectTypeValue == "flow":
        strProjectType: Str_ProjectType = "flow"
    elif projectTypeValue == "component":
        strProjectType = "component"
    else:
        raise ValueError("transaction.json projectType must be 'flow' or 'component'.")

    manifestFileValue = value.get("manifestFileName")
    strExpectedManifestFileName = get_manifest_file_name(strProjectType)
    if manifestFileValue != strExpectedManifestFileName:
        raise ValueError("transaction.json manifestFileName does not match projectType.")
    strManifestFileName = strExpectedManifestFileName

    dictSource = _validate_snapshot(value.get("source"), "source", isTarget=False)
    dictTarget = _validate_snapshot(value.get("target"), "target", isTarget=True)

    if operationValue == "applyDependencyPlan":
        assert strPlanSha256 is not None
        return {
            "schemaVersion": 1,
            "operation": "applyDependencyPlan",
            "state": transactionState,
            "projectType": strProjectType,
            "manifestFileName": strManifestFileName,
            "source": dictSource,
            "target": dictTarget,
            #
            "planSha256": strPlanSha256,
        }

    return {
        "schemaVersion": 1,
        "operation": "repairProjectComponents",
        "state": transactionState,
        "projectType": strProjectType,
        "manifestFileName": strManifestFileName,
        "source": dictSource,
        "target": dictTarget,
    }


def read_project_transaction(transactionFolderPath: Path) -> DictProjectTransaction:
    pathTransactionFile = transactionFolderPath / _STR_TRANSACTION_FILE_NAME
    if is_file_invalid(pathTransactionFile):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="A Project dependency transaction is missing a valid transaction.json.",
            details={"transactionFolderPath": str(transactionFolderPath)},
        )

    try:
        return _validate_project_transaction(read_json(pathTransactionFile))
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="A Project dependency transaction contains invalid metadata.",
            details={
                "transactionFolderPath": str(transactionFolderPath),
                "reason": str(e),
            },
        ) from e


def write_transaction_state(
    transactionFolderPath: Path,
    transactionDict: DictProjectTransaction,
    state: Str_ProjectTransaction_State,
) -> None:
    transactionDict["state"] = state

    try:
        write_json_atomic(
            transactionFolderPath / _STR_TRANSACTION_FILE_NAME,
            transactionDict,
        )
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="Failed to update the Project dependency transaction state.",
            details={
                "transactionFolderPath": str(transactionFolderPath),
                "state": state,
            },
        ) from e


def _remove_path(path: Path) -> None:
    if not path_exists(path):
        return

    if path.is_symlink() or path.is_file():
        path.unlink()
        return

    if path.is_dir():
        rmtree(path)
        return

    raise OSError(f"Unsupported path type: {path}")


def remove_transaction_folder(
    transactionFolderPath: Path,
) -> DictComponentManagementWarning | None:
    try:
        if path_exists(transactionFolderPath):
            if is_folder_invalid(transactionFolderPath):
                raise OSError("Transaction path is not a normal folder.")
            rmtree(transactionFolderPath)
    except OSError as e:
        return {
            "code": "project_transaction_cleanup_failed",
            "message": "The completed Project dependency transaction could not be removed.",
            "details": {
                "transactionFolderPath": str(transactionFolderPath),
                "reason": str(e),
            },
        }

    pathTransactions = transactionFolderPath.parent
    try:
        if (
            pathTransactions.is_dir()
            and not pathTransactions.is_symlink()
            and not any(pathTransactions.iterdir())
        ):
            pathTransactions.rmdir()
    except OSError:
        pass

    return None


def _copy_project_file_to_transaction(
    sourcePath: Path, targetPath: Path, field: str
) -> None:
    try:
        targetPath.parent.mkdir(parents=True, exist_ok=True)
        with sourcePath.open("rb") as sourceFileObj:
            with targetPath.open("xb") as targetFileObj:
                copyfileobj(sourceFileObj, targetFileObj)
                targetFileObj.flush()
                os.fsync(targetFileObj.fileno())
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message=f"Failed to copy {field}.",
            details={
                "sourcePath": str(sourcePath),
                "targetPath": str(targetPath),
            },
        ) from e


def get_regular_file_sha256(path: Path, field: str) -> str:
    if is_file_invalid(path):
        raise ComponentManagementError(
            code="project_transaction_failed",
            message=f"{field} is not a valid file.",
            details={"path": str(path)},
        )

    try:
        return calculate_file_sha256(path)
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message=f"Failed to read {field}.",
            details={"path": str(path)},
        ) from e


def _build_transaction_snapshot(
    manifestPath: Path,
    componentsLockFilePath: Path,
    componentsFolderPath: Path,
) -> DictProjectTransaction_Snapshot:
    boolComponentsLockFileShouldExist = path_exists(componentsLockFilePath)
    boolComponentsFolderShouldExist = path_exists(componentsFolderPath)

    if boolComponentsLockFileShouldExist and is_file_invalid(componentsLockFilePath):
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="The current components.lock.json path is invalid.",
            details={"componentsLockFilePath": str(componentsLockFilePath)},
        )

    dictSnapshot: DictProjectTransaction_Snapshot = {
        "manifestSha256": get_regular_file_sha256(manifestPath, "Project Manifest"),
        "componentsLockFileShouldExist": boolComponentsLockFileShouldExist,
        "componentsFolderShouldExist": boolComponentsFolderShouldExist,
    }
    if boolComponentsLockFileShouldExist:
        dictSnapshot["expectedComponentsLockFileSha256"] = get_regular_file_sha256(
            componentsLockFilePath,
            "components.lock.json",
        )

    return dictSnapshot


def prepare_project_transaction(
    projectPath: Path,
    repositoryPath: Path,
    *,
    transactionOperation: Literal["applyDependencyPlan", "repairProjectComponents"],
    projectType: Str_ProjectType,
    manifestFileName: Str_ManifestFileName,
    sourceManifestObj: Info_ProjectManifest,
    sourceComponentsLockDict: DictComponentsLock_File | None,
    targetManifestObj: Info_ProjectManifest,
    targetComponentsLockDict: DictComponentsLock_File | None,
    planSha256: str | None = None,
) -> tuple[Path, DictProjectTransaction]:
    pathManifestFile = projectPath / manifestFileName
    pathComponentsLockFile = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathComponentsFolder = projectPath / STR_COMPONENTS_FOLDER_NAME
    dictSourceSnapshot = _build_transaction_snapshot(
        pathManifestFile,
        pathComponentsLockFile,
        pathComponentsFolder,
    )

    pathTransactionsFolder = get_transactions_path(projectPath)
    strTransactionId = str(uuid.uuid4())
    pathTempTransactionFolder = (
        pathTransactionsFolder
        / f"{_STR_PROJECT_TRANSACTION_TEMP_PREFIX}{strTransactionId}{_STR_PROJECT_TRANSACTION_TEMP_SUFFIX}"
    )

    pathSpecificTransactionFolder = (
        pathTransactionsFolder / f"{STR_PROJECT_TRANSACTION_PREFIX}{strTransactionId}"
    )
    pathTempTargetFolder = pathTempTransactionFolder / STR_TARGET_FOLDER_NAME
    pathTempBackupFolder = pathTempTransactionFolder / STR_BACKUP_FOLDER_NAME

    try:
        pathTransactionsFolder.mkdir(parents=True, exist_ok=True)
        pathTempTransactionFolder.mkdir()
        pathTempTargetFolder.mkdir()
        pathTempBackupFolder.mkdir()

        pathTargetManifestFile = pathTempTargetFolder / manifestFileName
        if targetManifestObj == sourceManifestObj:
            # Preserve the exact source bytes when the target Manifest is unchanged so formatting alone does not create a different transaction target SHA-256.
            _copy_project_file_to_transaction(
                pathManifestFile,
                pathTargetManifestFile,
                "the current Project Manifest into the transaction target",
            )
        else:
            write_json_atomic(
                pathTargetManifestFile,
                build_project_manifest_dict(targetManifestObj),
            )

        pathTargetComponentsLockFile = (
            pathTempTargetFolder / STR_COMPONENTS_LOCK_FILE_NAME
        )
        pathTargetComponentsFolder = pathTempTargetFolder / STR_COMPONENTS_FOLDER_NAME
        if targetComponentsLockDict is not None:
            if targetComponentsLockDict == sourceComponentsLockDict:
                # Preserve the exact source bytes when the target lock is unchanged so formatting alone does not create a different transaction target SHA-256.
                _copy_project_file_to_transaction(
                    pathComponentsLockFile,
                    pathTargetComponentsLockFile,
                    "the current components.lock.json into the transaction target",
                )
            else:
                write_components_lock(
                    pathTargetComponentsLockFile, targetComponentsLockDict
                )

            build_components_folder(
                repositoryPath=repositoryPath,
                targetComponentsFolderPath=pathTargetComponentsFolder,
                lockDict=targetComponentsLockDict,
            )

        pathBackupManifestFile = pathTempBackupFolder / manifestFileName
        _copy_project_file_to_transaction(
            pathManifestFile,
            pathBackupManifestFile,
            "the current Project Manifest into the transaction backup",
        )

        dictTargetSnapshot = _build_transaction_snapshot(
            pathTargetManifestFile,
            pathTargetComponentsLockFile,
            pathTargetComponentsFolder,
        )
        if transactionOperation == "applyDependencyPlan":
            assert planSha256 is not None
            dictTransaction: DictProjectTransaction = {
                "schemaVersion": 1,
                "operation": "applyDependencyPlan",
                "state": "prepared",
                "projectType": projectType,
                "manifestFileName": manifestFileName,
                #
                "source": dictSourceSnapshot,
                "target": dictTargetSnapshot,
                #
                "planSha256": planSha256,
            }
        else:
            assert planSha256 is None
            dictTransaction = {
                "schemaVersion": 1,
                "operation": "repairProjectComponents",
                "state": "prepared",
                "projectType": projectType,
                "manifestFileName": manifestFileName,
                #
                "source": dictSourceSnapshot,
                "target": dictTargetSnapshot,
            }

        write_json_atomic(
            pathTempTransactionFolder / _STR_TRANSACTION_FILE_NAME,
            dictTransaction,
        )

        os.replace(pathTempTransactionFolder, pathSpecificTransactionFolder)
    except ComponentManagementError:
        raise
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="Failed to prepare the Project transaction.",
            details={"transactionFolderPath": str(pathTempTransactionFolder)},
        ) from e
    finally:
        if path_exists(pathTempTransactionFolder):
            try:
                _remove_path(pathTempTransactionFolder)
            except OSError:
                pass

    return pathSpecificTransactionFolder, dictTransaction


def move_source_to_backup(
    projectPath: Path,
    backupPath: Path,
    snapshotDict: DictProjectTransaction_Snapshot,
) -> None:
    pathProjectComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    pathBackupComponents = backupPath / STR_COMPONENTS_FOLDER_NAME
    if snapshotDict["componentsFolderShouldExist"]:
        os.replace(pathProjectComponents, pathBackupComponents)

    pathProjectLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathBackupLock = backupPath / STR_COMPONENTS_LOCK_FILE_NAME
    if snapshotDict["componentsLockFileShouldExist"]:
        os.replace(pathProjectLock, pathBackupLock)


def move_target_to_project(
    projectPath: Path,
    targetPath: Path,
    snapshotDict: DictProjectTransaction_Snapshot,
) -> None:
    if snapshotDict["componentsFolderShouldExist"]:
        os.replace(
            targetPath / STR_COMPONENTS_FOLDER_NAME,
            projectPath / STR_COMPONENTS_FOLDER_NAME,
        )

    if snapshotDict["componentsLockFileShouldExist"]:
        os.replace(
            targetPath / STR_COMPONENTS_LOCK_FILE_NAME,
            projectPath / STR_COMPONENTS_LOCK_FILE_NAME,
        )


def validate_target_project_state(
    projectPath: Path,
    transactionDict: DictProjectTransaction,
) -> Info_ProjectComponentsFolder | None:
    strProjectType, _ = read_project_manifest(projectPath)
    if strProjectType != transactionDict["projectType"]:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="The recovered Project Manifest type does not match transaction.json.",
            details={"projectPath": str(projectPath)},
        )

    pathManifest = projectPath / transactionDict["manifestFileName"]
    strManifestSha256 = get_regular_file_sha256(pathManifest, "Project Manifest")
    if strManifestSha256 != transactionDict["target"]["manifestSha256"]:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="The Project Manifest does not match the committed transaction target.",
            details={
                "manifestPath": str(pathManifest),
                "expectedSha256": transactionDict["target"]["manifestSha256"],
                "actualSha256": strManifestSha256,
            },
        )

    pathLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    dictTarget = transactionDict["target"]

    if not dictTarget["componentsLockFileShouldExist"]:
        if path_exists(pathLock) or path_exists(pathComponents):
            raise ComponentManagementError(
                code="project_transaction_recovery_failed",
                message="The committed Project should not contain dependency lock artifacts.",
                details={"projectPath": str(projectPath)},
            )
        return None

    strExpectedLockSha256 = dictTarget.get("expectedComponentsLockFileSha256")
    assert strExpectedLockSha256 is not None

    strLockSha256 = get_regular_file_sha256(pathLock, "components.lock.json")
    if strLockSha256 != strExpectedLockSha256:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="The committed components.lock.json does not match transaction.json.",
            details={
                "lockFile": str(pathLock),
                "expectedSha256": strExpectedLockSha256,
                "actualSha256": strLockSha256,
            },
        )

    dictLock = read_components_lock(pathLock)
    return validate_components_folder(pathComponents, dictLock)


def restore_source_entry(
    projectEntryPath: Path,
    transactionBackupEntryPath: Path,
    *,
    sourceShouldExist: bool,
    expectedSourceSha256: str | None = None,
) -> None:
    """
    Restore one Project entry to the source snapshot during transaction rollback.

    If a backup exists, replace any partially committed target entry with the backed-up source entry.

    If no backup exists but the source snapshot requires the entry, the original entry should still be at its Project path because the backup move had not occurred before the interruption.

    If the source snapshot does not require the entry, remove any partially committed target entry from the Project.
    """

    boolProjectEntryExists = path_exists(projectEntryPath)
    boolTransactionBackupEntryExists = path_exists(transactionBackupEntryPath)

    if boolTransactionBackupEntryExists:
        # The commit already moved the source entry into backup. Remove any partially committed target entry and restore the source entry.
        _remove_path(projectEntryPath)
        os.replace(transactionBackupEntryPath, projectEntryPath)
    elif sourceShouldExist:
        # No backup means the source entry had not yet been moved when the interruption occurred. It must therefore still be in the Project.
        if not boolProjectEntryExists:
            raise OSError(
                f"The source entry and its transaction backup are both missing: {projectEntryPath}."
            )
    else:
        # The source snapshot did not contain this entry. Remove anything that was partially committed to the Project.
        _remove_path(projectEntryPath)

    if sourceShouldExist and expectedSourceSha256 is not None:
        # File entries with a recorded SHA-256 must exactly match the source snapshot after restoration.
        strActualSha256 = get_regular_file_sha256(projectEntryPath, projectEntryPath.name)
        if strActualSha256 != expectedSourceSha256:
            raise OSError(
                f"Restored file SHA-256 does not match for {projectEntryPath}: "
                f"expected {expectedSourceSha256}, actual {strActualSha256}."
            )


def ensure_target_entry_committed(
    projectEntryPath: Path,
    transactionTargetEntryPath: Path,
    *,
    targetShouldExist: bool,
) -> None:
    """
    Ensure one Project entry matches the target snapshot during forward recovery.

    If the target snapshot requires the entry, keep it when it has already been committed to the Project. Otherwise, move the remaining staged target entry from the transaction folder into the Project.

    If the target snapshot does not require the entry, remove any source or partially committed entry left at the Project path.
    """

    boolProjectEntryExists = path_exists(projectEntryPath)
    boolTransactionTargetEntryExists = path_exists(transactionTargetEntryPath)

    if targetShouldExist:
        if not boolProjectEntryExists:
            # The target entry was already moved into the Project before the interruption. Final state validation will verify its contents.
            return None
        if not boolTransactionTargetEntryExists:
            # Neither location contains the required target entry, so the committed Project state cannot be reconstructed.
            raise OSError(
                f"The target entry is missing from both the Project and transaction staging: {projectEntryPath}."
            )
        # The target entry is still staged in the transaction folder. Complete the interrupted move into the Project.
        os.replace(transactionTargetEntryPath, projectEntryPath)
        return None

    # The target snapshot intentionally omits this entry. Remove any source or partially committed target entry left in the Project.
    _remove_path(projectEntryPath)


def cleanup_temporary_transaction_folders(
    transactionFolderPath: Path,
) -> list[DictComponentManagementWarning]:
    listWarning: list[DictComponentManagementWarning] = []

    for pathEntry_InnerTransactionFolder in sorted(
        transactionFolderPath.iterdir(), key=lambda pathObj: pathObj.name
    ):
        if not (
            pathEntry_InnerTransactionFolder.name.startswith(
                _STR_PROJECT_TRANSACTION_TEMP_PREFIX
            )
            and pathEntry_InnerTransactionFolder.name.endswith(
                _STR_PROJECT_TRANSACTION_TEMP_SUFFIX
            )
        ):
            continue

        try:
            if is_folder_invalid(pathEntry_InnerTransactionFolder):
                raise OSError("Temporary transaction path is not a normal folder.")
            rmtree(pathEntry_InnerTransactionFolder)
        except OSError as e:
            listWarning.append({
                "code": "project_transaction_cleanup_failed",
                "message": "An incomplete Project transaction preparation folder could not be removed.",
                "details": {
                    "transactionFolderPath": str(pathEntry_InnerTransactionFolder),
                    "reason": str(e),
                },
            })

    return listWarning
