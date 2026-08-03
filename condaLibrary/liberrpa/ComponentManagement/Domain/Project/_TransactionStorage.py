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
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest
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

_SET_TRANSACTION_BASE_KEYS = {
    "schemaVersion",
    "operation",
    "state",
    "projectType",
    "manifestFile",
    "source",
    "target",
}
_SET_APPLY_TRANSACTION_KEYS = _SET_TRANSACTION_BASE_KEYS | {"planSha256"}
_SET_REPAIR_TRANSACTION_KEYS = set(_SET_TRANSACTION_BASE_KEYS)
_SET_SNAPSHOT_BASE_KEYS = {
    "manifestSha256",
    "componentsLockExists",
    "componentsPathExists",
}


def get_transactions_path(projectPath: Path) -> Path:
    return projectPath / _STR_INTERNAL_FOLDER_NAME / _STR_TRANSACTIONS_FOLDER_NAME


def get_manifest_file(projectType: Literal["flow", "component"]) -> Literal["flow.json", "component.json"]:
    return "flow.json" if projectType == "flow" else "component.json"


def _validate_snapshot(
    value: object,
    field: str,
    *,
    isTarget: bool,
) -> DictProjectTransaction_Snapshot:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    boolComponentsLockExists = value.get("componentsLockExists")
    if type(boolComponentsLockExists) is not bool:
        raise ValueError(f"{field}.componentsLockExists must be a boolean.")

    setExpectedKey = set(_SET_SNAPSHOT_BASE_KEYS)
    if boolComponentsLockExists:
        setExpectedKey.add("componentsLockSha256")
    validate_exact_keys(value, setExpectedKey, field)

    strManifestSha256 = validate_sha256(
        value.get("manifestSha256"),
        f"{field}.manifestSha256",
    )

    boolComponentsPathExists = value.get("componentsPathExists")
    if type(boolComponentsPathExists) is not bool:
        raise ValueError(f"{field}.componentsPathExists must be a boolean.")

    if isTarget and boolComponentsLockExists != boolComponentsPathExists:
        raise ValueError(f"{field}.componentsLockExists and {field}.componentsPathExists must have the same value.")

    dictSnapshot: DictProjectTransaction_Snapshot = {
        "manifestSha256": strManifestSha256,
        "componentsLockExists": boolComponentsLockExists,
        "componentsPathExists": boolComponentsPathExists,
    }

    if boolComponentsLockExists:
        dictSnapshot["componentsLockSha256"] = validate_sha256(
            value.get("componentsLockSha256"),
            f"{field}.componentsLockSha256",
        )

    return dictSnapshot


def _validate_project_transaction(value: object) -> DictProjectTransaction:
    if not isinstance(value, dict):
        raise ValueError("Project transaction root value must be an object.")

    operationValue = value.get("operation")
    if operationValue == "applyDependencyPlan":
        validate_exact_keys(value, _SET_APPLY_TRANSACTION_KEYS, "transaction.json")
        strPlanSha256 = validate_sha256(value.get("planSha256"), "planSha256")
    elif operationValue == "repairProjectComponents":
        validate_exact_keys(value, _SET_REPAIR_TRANSACTION_KEYS, "transaction.json")
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
        strProjectType: Literal["flow", "component"] = "flow"
    elif projectTypeValue == "component":
        strProjectType = "component"
    else:
        raise ValueError("transaction.json projectType must be 'flow' or 'component'.")

    manifestFileValue = value.get("manifestFile")
    strExpectedManifestFile = get_manifest_file(strProjectType)
    if manifestFileValue != strExpectedManifestFile:
        raise ValueError("transaction.json manifestFile does not match projectType.")
    strManifestFile: Literal["flow.json", "component.json"] = strExpectedManifestFile

    dictSource = _validate_snapshot(value.get("source"), "source", isTarget=False)
    dictTarget = _validate_snapshot(value.get("target"), "target", isTarget=True)

    if operationValue == "applyDependencyPlan":
        assert strPlanSha256 is not None
        return {
            "schemaVersion": 1,
            "operation": "applyDependencyPlan",
            "state": transactionState,
            "projectType": strProjectType,
            "manifestFile": strManifestFile,
            "planSha256": strPlanSha256,
            "source": dictSource,
            "target": dictTarget,
        }

    return {
        "schemaVersion": 1,
        "operation": "repairProjectComponents",
        "state": transactionState,
        "projectType": strProjectType,
        "manifestFile": strManifestFile,
        "source": dictSource,
        "target": dictTarget,
    }


def read_project_transaction(transactionPath: Path) -> DictProjectTransaction:
    pathTransactionFile = transactionPath / _STR_TRANSACTION_FILE_NAME
    if is_file_invalid(pathTransactionFile):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="A Project dependency transaction is missing a valid transaction.json.",
            details={"transactionPath": str(transactionPath)},
        )

    try:
        return _validate_project_transaction(read_json(pathTransactionFile))
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="A Project dependency transaction contains invalid metadata.",
            details={
                "transactionPath": str(transactionPath),
                "reason": str(e),
            },
        ) from e


def write_transaction_state(
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
    state: Str_ProjectTransaction_State,
) -> None:
    transactionDict["state"] = state

    try:
        write_json_atomic(
            transactionPath / _STR_TRANSACTION_FILE_NAME,
            transactionDict,
        )
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="Failed to update the Project dependency transaction state.",
            details={
                "transactionPath": str(transactionPath),
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
    transactionPath: Path,
) -> DictComponentManagementWarning | None:
    try:
        if path_exists(transactionPath):
            if is_folder_invalid(transactionPath):
                raise OSError("Transaction path is not a normal folder.")
            rmtree(transactionPath)
    except OSError as e:
        return {
            "code": "project_transaction_cleanup_failed",
            "message": "The completed Project dependency transaction could not be removed.",
            "details": {
                "transactionPath": str(transactionPath),
                "reason": str(e),
            },
        }

    pathTransactions = transactionPath.parent
    try:
        if pathTransactions.is_dir() and not pathTransactions.is_symlink() and not any(pathTransactions.iterdir()):
            pathTransactions.rmdir()
    except OSError:
        pass

    return None


def _copy_regular_file(sourcePath: Path, targetPath: Path, field: str) -> None:
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
    lockPath: Path,
    componentsPath: Path,
) -> DictProjectTransaction_Snapshot:
    boolLockExists = path_exists(lockPath)
    boolComponentsPathExists = path_exists(componentsPath)

    if boolLockExists and is_file_invalid(lockPath):
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="The current components.lock.json path is invalid.",
            details={"lockFile": str(lockPath)},
        )

    dictSnapshot: DictProjectTransaction_Snapshot = {
        "manifestSha256": get_regular_file_sha256(manifestPath, "Project Manifest"),
        "componentsLockExists": boolLockExists,
        "componentsPathExists": boolComponentsPathExists,
    }
    if boolLockExists:
        dictSnapshot["componentsLockSha256"] = get_regular_file_sha256(
            lockPath,
            "components.lock.json",
        )

    return dictSnapshot


def prepare_project_transaction(
    projectPath: Path,
    repositoryPath: Path,
    *,
    transactionOperation: Literal["applyDependencyPlan", "repairProjectComponents"],
    projectType: Literal["flow", "component"],
    manifestFile: Literal["flow.json", "component.json"],
    sourceManifestObj: Info_ProjectManifest,
    sourceComponentsLock: DictComponentsLock_File | None,
    targetManifestObj: Info_ProjectManifest,
    targetComponentsLock: DictComponentsLock_File | None,
    planSha256: str | None = None,
) -> tuple[Path, DictProjectTransaction]:
    pathManifest = projectPath / manifestFile
    pathLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    dictSourceSnapshot = _build_transaction_snapshot(
        pathManifest,
        pathLock,
        pathComponents,
    )

    pathTransactions = get_transactions_path(projectPath)
    strTransactionId = str(uuid.uuid4())
    pathTempTransaction = pathTransactions / (
        f"{_STR_PROJECT_TRANSACTION_TEMP_PREFIX}{strTransactionId}{_STR_PROJECT_TRANSACTION_TEMP_SUFFIX}"
    )
    pathTransaction = pathTransactions / f"{STR_PROJECT_TRANSACTION_PREFIX}{strTransactionId}"
    pathTarget = pathTempTransaction / STR_TARGET_FOLDER_NAME
    pathBackup = pathTempTransaction / STR_BACKUP_FOLDER_NAME

    try:
        pathTransactions.mkdir(parents=True, exist_ok=True)
        pathTempTransaction.mkdir()
        pathTarget.mkdir()
        pathBackup.mkdir()

        pathTargetManifest = pathTarget / manifestFile
        if targetManifestObj == sourceManifestObj:
            _copy_regular_file(
                pathManifest,
                pathTargetManifest,
                "the current Project Manifest into the transaction target",
            )
        else:
            write_json_atomic(
                pathTargetManifest,
                build_project_manifest_dict(targetManifestObj),
            )

        pathTargetLock = pathTarget / STR_COMPONENTS_LOCK_FILE_NAME
        pathTargetComponents = pathTarget / STR_COMPONENTS_FOLDER_NAME
        if targetComponentsLock is not None:
            if targetComponentsLock == sourceComponentsLock:
                _copy_regular_file(
                    pathLock,
                    pathTargetLock,
                    "the current components.lock.json into the transaction target",
                )
            else:
                write_components_lock(pathTargetLock, targetComponentsLock)

            build_components_folder(
                repositoryPath=repositoryPath,
                targetPath=pathTargetComponents,
                lockDict=targetComponentsLock,
            )

        pathBackupManifest = pathBackup / manifestFile
        _copy_regular_file(
            pathManifest,
            pathBackupManifest,
            "the current Project Manifest into the transaction backup",
        )

        dictTargetSnapshot = _build_transaction_snapshot(
            pathTargetManifest,
            pathTargetLock,
            pathTargetComponents,
        )
        if transactionOperation == "applyDependencyPlan":
            assert planSha256 is not None
            dictTransaction: DictProjectTransaction = {
                "schemaVersion": 1,
                "operation": "applyDependencyPlan",
                "state": "prepared",
                "projectType": projectType,
                "manifestFile": manifestFile,
                "planSha256": planSha256,
                "source": dictSourceSnapshot,
                "target": dictTargetSnapshot,
            }
        else:
            assert planSha256 is None
            dictTransaction = {
                "schemaVersion": 1,
                "operation": "repairProjectComponents",
                "state": "prepared",
                "projectType": projectType,
                "manifestFile": manifestFile,
                "source": dictSourceSnapshot,
                "target": dictTargetSnapshot,
            }

        write_json_atomic(
            pathTempTransaction / _STR_TRANSACTION_FILE_NAME,
            dictTransaction,
        )

        os.replace(pathTempTransaction, pathTransaction)
    except ComponentManagementError:
        raise
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="Failed to prepare the Project transaction.",
            details={"transactionPath": str(pathTempTransaction)},
        ) from e
    finally:
        if path_exists(pathTempTransaction):
            try:
                _remove_path(pathTempTransaction)
            except OSError:
                pass

    return pathTransaction, dictTransaction


def move_source_to_backup(
    projectPath: Path,
    backupPath: Path,
    snapshotDict: DictProjectTransaction_Snapshot,
) -> None:
    pathProjectComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    pathBackupComponents = backupPath / STR_COMPONENTS_FOLDER_NAME
    if snapshotDict["componentsPathExists"]:
        os.replace(pathProjectComponents, pathBackupComponents)

    pathProjectLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathBackupLock = backupPath / STR_COMPONENTS_LOCK_FILE_NAME
    if snapshotDict["componentsLockExists"]:
        os.replace(pathProjectLock, pathBackupLock)


def move_target_to_project(
    projectPath: Path,
    targetPath: Path,
    snapshotDict: DictProjectTransaction_Snapshot,
) -> None:
    if snapshotDict["componentsPathExists"]:
        os.replace(
            targetPath / STR_COMPONENTS_FOLDER_NAME,
            projectPath / STR_COMPONENTS_FOLDER_NAME,
        )

    if snapshotDict["componentsLockExists"]:
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

    pathManifest = projectPath / transactionDict["manifestFile"]
    strManifestSha256 = get_regular_file_sha256(pathManifest, "Project Manifest")
    if strManifestSha256 != transactionDict["target"]["manifestSha256"]:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="The Project Manifest does not match the committed transaction target.",
            details={
                "manifestFile": str(pathManifest),
                "expectedSha256": transactionDict["target"]["manifestSha256"],
                "actualSha256": strManifestSha256,
            },
        )

    pathLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    dictTarget = transactionDict["target"]

    if not dictTarget["componentsLockExists"]:
        if path_exists(pathLock) or path_exists(pathComponents):
            raise ComponentManagementError(
                code="project_transaction_recovery_failed",
                message="The committed Project should not contain dependency lock artifacts.",
                details={"projectPath": str(projectPath)},
            )
        return None

    strExpectedLockSha256 = dictTarget.get("componentsLockSha256")
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


def restore_source_path(
    projectPath: Path,
    backupPath: Path,
    *,
    sourceExists: bool,
    sourceSha256: str | None = None,
) -> None:
    boolProjectExists = path_exists(projectPath)
    boolBackupExists = path_exists(backupPath)

    if boolBackupExists:
        _remove_path(projectPath)
        os.replace(backupPath, projectPath)
    elif sourceExists:
        if not boolProjectExists:
            raise OSError(f"Source backup is missing for {projectPath}.")
    else:
        _remove_path(projectPath)

    if sourceExists and sourceSha256 is not None:
        strActualSha256 = get_regular_file_sha256(projectPath, projectPath.name)
        if strActualSha256 != sourceSha256:
            raise OSError(
                f"Restored file SHA-256 does not match for {projectPath}: "
                f"expected {sourceSha256}, actual {strActualSha256}."
            )


def ensure_target_path_committed(
    projectPath: Path,
    targetPath: Path,
    *,
    targetExists: bool,
) -> None:
    boolProjectExists = path_exists(projectPath)
    boolTargetExists = path_exists(targetPath)

    if targetExists:
        if not boolProjectExists:
            if not boolTargetExists:
                raise OSError(f"Transaction target is missing for {projectPath}.")
            os.replace(targetPath, projectPath)
    else:
        _remove_path(projectPath)


def cleanup_temporary_transaction_folders(
    transactionsPath: Path,
) -> list[DictComponentManagementWarning]:
    listWarning: list[DictComponentManagementWarning] = []

    for pathEntry in sorted(transactionsPath.iterdir(), key=lambda pathObj: pathObj.name):
        if not (
            pathEntry.name.startswith(_STR_PROJECT_TRANSACTION_TEMP_PREFIX)
            and pathEntry.name.endswith(_STR_PROJECT_TRANSACTION_TEMP_SUFFIX)
        ):
            continue

        try:
            if is_folder_invalid(pathEntry):
                raise OSError("Temporary transaction path is not a normal folder.")
            rmtree(pathEntry)
        except OSError as e:
            listWarning.append({
                "code": "project_transaction_cleanup_failed",
                "message": "An incomplete Project transaction preparation folder could not be removed.",
                "details": {
                    "transactionPath": str(pathEntry),
                    "reason": str(e),
                },
            })

    return listWarning
