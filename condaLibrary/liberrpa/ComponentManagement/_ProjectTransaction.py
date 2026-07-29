# FileName: _ProjectTransaction.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Lock._ProjectLock import project_lock
from liberrpa.ComponentManagement.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import read_json, write_json_atomic
from liberrpa.ComponentManagement.Utils._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Utils._TypedValue import (
    ProjectManifest,
    DictComponentManagementWarning,
    DictComponentsLockFile,
    ComponentsFolderInfo,
    ProjectDependencyOperation,
    ProjectDependencyPlan,
    ProjectTransactionState,
    DictProjectTransactionSnapshot,
    DictProjectTransaction,
    ProjectDependencyApplyResult,
)
from liberrpa.ComponentManagement.Utils._Validation import (
    validate_exact_keys,
    path_exists,
    file_invalid,
    folder_invalid,
)
from liberrpa.ComponentManagement._Components import (
    STR_COMPONENTS_FOLDER_NAME,
    build_components_folder,
    validate_components_folder,
)
from liberrpa.ComponentManagement._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    is_components_lock_stale,
    read_components_lock,
    write_components_lock,
)
from liberrpa.ComponentManagement._DependencyPlan import build_project_dependency_plan
from liberrpa.ComponentManagement._Manifest import (
    build_project_manifest_dict,
    read_project_manifest,
)
from liberrpa.ComponentManagement._Repository import get_repository_path
from liberrpa.ComponentManagement._RepositoryIndex import (
    load_repository_index,
    validate_sha256,
)
from liberrpa.ComponentManagement._RepositoryTransaction import recover_publish_transactions

from pathlib import Path
from shutil import copyfileobj, rmtree
from typing import Literal
import os
import uuid


"""
Project dependency changes use a same-volume transaction inside the Project:

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
_STR_TARGET_FOLDER_NAME = "target"
_STR_BACKUP_FOLDER_NAME = "backup"
_STR_PROJECT_TRANSACTION_PREFIX = "project_"
_STR_PROJECT_TRANSACTION_TEMP_PREFIX = ".project_"
_STR_PROJECT_TRANSACTION_TEMP_SUFFIX = ".tmp"

_SET_TRANSACTION_KEYS = {
    "schemaVersion",
    "operation",
    "state",
    "projectType",
    "manifestFile",
    "planSha256",
    "source",
    "target",
}
_SET_SNAPSHOT_BASE_KEYS = {
    "manifestSha256",
    "componentsLockExists",
    "componentsPathExists",
}


def _resolve_project_path(projectPath: Path) -> Path:
    try:
        pathProject = projectPath.expanduser().resolve()
    except (OSError, RuntimeError) as e:
        raise ComponentManagementError(
            code="project_path_invalid",
            message=f"Failed to resolve the Project path: {projectPath}",
        ) from e

    if not pathProject.is_dir():
        raise ComponentManagementError(
            code="project_path_invalid",
            message=f"Project folder was not found: {pathProject}",
        )

    return pathProject


def _get_transactions_path(projectPath: Path) -> Path:
    return projectPath / _STR_INTERNAL_FOLDER_NAME / _STR_TRANSACTIONS_FOLDER_NAME


def _get_manifest_file(projectType: Literal["flow", "component"]) -> Literal["flow.json", "component.json"]:
    return "flow.json" if projectType == "flow" else "component.json"


def _validate_snapshot(
    value: object,
    field: str,
    *,
    isTarget: bool,
) -> DictProjectTransactionSnapshot:
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

    dictSnapshot: DictProjectTransactionSnapshot = {
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

    validate_exact_keys(value, _SET_TRANSACTION_KEYS, "transaction.json")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("transaction.json schemaVersion must be 1.")

    if value.get("operation") != "applyDependencyPlan":
        raise ValueError("transaction.json operation must be 'applyDependencyPlan'.")

    transactionStateValue = value.get("state")
    if transactionStateValue == "prepared":
        transactionState: ProjectTransactionState = "prepared"
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
    strExpectedManifestFile = _get_manifest_file(strProjectType)
    if manifestFileValue != strExpectedManifestFile:
        raise ValueError("transaction.json manifestFile does not match projectType.")
    strManifestFile: Literal["flow.json", "component.json"] = strExpectedManifestFile

    strPlanSha256 = validate_sha256(value.get("planSha256"), "planSha256")
    dictSource = _validate_snapshot(value.get("source"), "source", isTarget=False)
    dictTarget = _validate_snapshot(value.get("target"), "target", isTarget=True)

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


def _read_project_transaction(transactionPath: Path) -> DictProjectTransaction:
    pathTransactionFile = transactionPath / _STR_TRANSACTION_FILE_NAME
    if file_invalid(pathTransactionFile):
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


def _write_transaction_state(
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
    state: ProjectTransactionState,
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


def _remove_transaction_folder(
    transactionPath: Path,
) -> DictComponentManagementWarning | None:
    try:
        if path_exists(transactionPath):
            if folder_invalid(transactionPath):
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


def _copy_source_manifest(sourcePath: Path, backupPath: Path) -> None:
    try:
        backupPath.parent.mkdir(parents=True, exist_ok=True)
        with sourcePath.open("rb") as sourceFileObj:
            with backupPath.open("xb") as backupFileObj:
                copyfileobj(sourceFileObj, backupFileObj)
                backupFileObj.flush()
                os.fsync(backupFileObj.fileno())
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="Failed to back up the current Project Manifest.",
            details={
                "manifestFile": str(sourcePath),
                "backupFile": str(backupPath),
            },
        ) from e


def _get_regular_file_sha256(path: Path, field: str) -> str:
    if file_invalid(path):
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


def _validate_source_project_state(
    projectPath: Path,
    planObj: ProjectDependencyPlan,
) -> tuple[Literal["flow", "component"], Literal["flow.json", "component.json"]]:
    strProjectType, currentManifestObj = read_project_manifest(projectPath)
    if currentManifestObj != planObj.sourceManifest:
        raise ComponentManagementError(
            code="dependency_plan_changed",
            message="The Project Manifest changed after the dependency plan was created.",
            details={"planSha256": planObj.planSha256},
        )

    strManifestFile = _get_manifest_file(strProjectType)
    pathLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME

    if planObj.sourceComponentsLock is not None:
        dictCurrentLock = read_components_lock(pathLock)
        if dictCurrentLock != planObj.sourceComponentsLock:
            raise ComponentManagementError(
                code="dependency_plan_changed",
                message="components.lock.json changed after the dependency plan was created.",
                details={"planSha256": planObj.planSha256},
            )
    elif currentManifestObj.componentDependencies:
        raise ComponentManagementError(
            code="dependency_plan_changed",
            message="The dependency plan does not contain the lock required by the current Project Manifest.",
            details={"planSha256": planObj.planSha256},
        )

    return strProjectType, strManifestFile


def _build_transaction_snapshot(
    manifestPath: Path,
    lockPath: Path,
    componentsPath: Path,
) -> DictProjectTransactionSnapshot:
    boolLockExists = path_exists(lockPath)
    boolComponentsPathExists = path_exists(componentsPath)

    if boolLockExists and file_invalid(lockPath):
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="The current components.lock.json path is invalid.",
            details={"lockFile": str(lockPath)},
        )

    if boolComponentsPathExists and folder_invalid(componentsPath):
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="The current _Components path is invalid.",
            details={"componentsPath": str(componentsPath)},
        )

    dictSnapshot: DictProjectTransactionSnapshot = {
        "manifestSha256": _get_regular_file_sha256(manifestPath, "Project Manifest"),
        "componentsLockExists": boolLockExists,
        "componentsPathExists": boolComponentsPathExists,
    }
    if boolLockExists:
        dictSnapshot["componentsLockSha256"] = _get_regular_file_sha256(
            lockPath,
            "components.lock.json",
        )

    return dictSnapshot


def _prepare_project_transaction(
    projectPath: Path,
    repositoryPath: Path,
    planObj: ProjectDependencyPlan,
) -> tuple[Path, DictProjectTransaction]:
    strProjectType, strManifestFile = _validate_source_project_state(projectPath, planObj)
    pathManifest = projectPath / strManifestFile
    pathLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    dictSourceSnapshot = _build_transaction_snapshot(
        pathManifest,
        pathLock,
        pathComponents,
    )

    pathTransactions = _get_transactions_path(projectPath)
    strTransactionId = str(uuid.uuid4())
    pathTempTransaction = pathTransactions / (
        f"{_STR_PROJECT_TRANSACTION_TEMP_PREFIX}{strTransactionId}{_STR_PROJECT_TRANSACTION_TEMP_SUFFIX}"
    )
    pathTransaction = pathTransactions / f"{_STR_PROJECT_TRANSACTION_PREFIX}{strTransactionId}"
    pathTarget = pathTempTransaction / _STR_TARGET_FOLDER_NAME
    pathBackup = pathTempTransaction / _STR_BACKUP_FOLDER_NAME

    try:
        pathTransactions.mkdir(parents=True, exist_ok=True)
        pathTempTransaction.mkdir()
        pathTarget.mkdir()
        pathBackup.mkdir()

        pathTargetManifest = pathTarget / strManifestFile
        write_json_atomic(
            pathTargetManifest,
            build_project_manifest_dict(planObj.targetManifest),
        )

        pathTargetLock = pathTarget / STR_COMPONENTS_LOCK_FILE_NAME
        pathTargetComponents = pathTarget / STR_COMPONENTS_FOLDER_NAME
        if planObj.targetComponentsLock is not None:
            write_components_lock(pathTargetLock, planObj.targetComponentsLock)
            build_components_folder(
                repositoryPath=repositoryPath,
                targetPath=pathTargetComponents,
                lockDict=planObj.targetComponentsLock,
            )

        pathBackupManifest = pathBackup / strManifestFile
        _copy_source_manifest(pathManifest, pathBackupManifest)

        dictTargetSnapshot = _build_transaction_snapshot(
            pathTargetManifest,
            pathTargetLock,
            pathTargetComponents,
        )
        dictTransaction: DictProjectTransaction = {
            "schemaVersion": 1,
            "operation": "applyDependencyPlan",
            "state": "prepared",
            "projectType": strProjectType,
            "manifestFile": strManifestFile,
            "planSha256": planObj.planSha256,
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
            message="Failed to prepare the Project dependency transaction.",
            details={"transactionPath": str(pathTempTransaction)},
        ) from e
    finally:
        if pathTempTransaction.exists() and not pathTempTransaction.is_symlink():
            rmtree(pathTempTransaction, ignore_errors=True)

    return pathTransaction, dictTransaction


def _move_source_to_backup(
    projectPath: Path,
    backupPath: Path,
    snapshotDict: DictProjectTransactionSnapshot,
) -> None:
    pathProjectComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    pathBackupComponents = backupPath / STR_COMPONENTS_FOLDER_NAME
    if snapshotDict["componentsPathExists"]:
        os.replace(pathProjectComponents, pathBackupComponents)

    pathProjectLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    pathBackupLock = backupPath / STR_COMPONENTS_LOCK_FILE_NAME
    if snapshotDict["componentsLockExists"]:
        os.replace(pathProjectLock, pathBackupLock)


def _move_target_to_project(
    projectPath: Path,
    targetPath: Path,
    snapshotDict: DictProjectTransactionSnapshot,
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


def _validate_target_project_state(
    projectPath: Path,
    transactionDict: DictProjectTransaction,
) -> ComponentsFolderInfo | None:
    strProjectType, _ = read_project_manifest(projectPath)
    if strProjectType != transactionDict["projectType"]:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="The recovered Project Manifest type does not match transaction.json.",
            details={"projectPath": str(projectPath)},
        )

    pathManifest = projectPath / transactionDict["manifestFile"]
    strManifestSha256 = _get_regular_file_sha256(pathManifest, "Project Manifest")
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

    strLockSha256 = _get_regular_file_sha256(pathLock, "components.lock.json")
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


def _commit_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> ComponentsFolderInfo | None:
    pathTarget = transactionPath / _STR_TARGET_FOLDER_NAME
    pathBackup = transactionPath / _STR_BACKUP_FOLDER_NAME
    pathManifest = projectPath / transactionDict["manifestFile"]

    try:
        _write_transaction_state(
            transactionPath,
            transactionDict,
            "committing",
        )
        _move_source_to_backup(
            projectPath,
            pathBackup,
            transactionDict["source"],
        )
        _move_target_to_project(
            projectPath,
            pathTarget,
            transactionDict["target"],
        )
        os.replace(
            pathTarget / transactionDict["manifestFile"],
            pathManifest,
        )
        _write_transaction_state(
            transactionPath,
            transactionDict,
            "manifestCommitted",
        )
    except ComponentManagementError:
        raise
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="Failed to commit the Project dependency transaction.",
            details={"transactionPath": str(transactionPath)},
        ) from e

    return _validate_target_project_state(projectPath, transactionDict)


def _restore_source_path(
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
        strActualSha256 = _get_regular_file_sha256(projectPath, projectPath.name)
        if strActualSha256 != sourceSha256:
            raise OSError(
                f"Restored file SHA-256 does not match for {projectPath}: "
                f"expected {sourceSha256}, actual {strActualSha256}."
            )


def _rollback_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> None:
    pathBackup = transactionPath / _STR_BACKUP_FOLDER_NAME
    dictSource = transactionDict["source"]

    try:
        _restore_source_path(
            projectPath / STR_COMPONENTS_FOLDER_NAME,
            pathBackup / STR_COMPONENTS_FOLDER_NAME,
            sourceExists=dictSource["componentsPathExists"],
        )
        _restore_source_path(
            projectPath / STR_COMPONENTS_LOCK_FILE_NAME,
            pathBackup / STR_COMPONENTS_LOCK_FILE_NAME,
            sourceExists=dictSource["componentsLockExists"],
            sourceSha256=dictSource.get("componentsLockSha256"),
        )
        _restore_source_path(
            projectPath / transactionDict["manifestFile"],
            pathBackup / transactionDict["manifestFile"],
            sourceExists=True,
            sourceSha256=dictSource["manifestSha256"],
        )
    except (ComponentManagementError, OSError) as e:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="Failed to roll back an interrupted Project dependency transaction.",
            details={
                "transactionPath": str(transactionPath),
                "reason": str(e),
            },
        ) from e


def _ensure_target_path_committed(
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


def _finish_committed_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> ComponentsFolderInfo | None:
    pathTarget = transactionPath / _STR_TARGET_FOLDER_NAME
    dictTarget = transactionDict["target"]

    try:
        _ensure_target_path_committed(
            projectPath / STR_COMPONENTS_FOLDER_NAME,
            pathTarget / STR_COMPONENTS_FOLDER_NAME,
            targetExists=dictTarget["componentsPathExists"],
        )
        _ensure_target_path_committed(
            projectPath / STR_COMPONENTS_LOCK_FILE_NAME,
            pathTarget / STR_COMPONENTS_LOCK_FILE_NAME,
            targetExists=dictTarget["componentsLockExists"],
        )
        _ensure_target_path_committed(
            projectPath / transactionDict["manifestFile"],
            pathTarget / transactionDict["manifestFile"],
            targetExists=True,
        )

        folderInfo = _validate_target_project_state(projectPath, transactionDict)
        if transactionDict["state"] != "manifestCommitted":
            _write_transaction_state(
                transactionPath,
                transactionDict,
                "manifestCommitted",
            )
        return folderInfo
    except (ComponentManagementError, OSError) as e:
        if isinstance(e, ComponentManagementError) and e.code == "project_transaction_recovery_failed":
            raise

        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="Failed to finish an interrupted committed Project dependency transaction.",
            details={
                "transactionPath": str(transactionPath),
                "reason": str(e),
            },
        ) from e


def _get_current_manifest_sha256(
    projectPath: Path,
    manifestFile: str,
) -> str | None:
    pathManifest = projectPath / manifestFile
    if not path_exists(pathManifest):
        return None

    return _get_regular_file_sha256(pathManifest, "Project Manifest")


def _recover_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> ComponentsFolderInfo | None:
    strCurrentManifestSha256 = _get_current_manifest_sha256(
        projectPath,
        transactionDict["manifestFile"],
    )
    strSourceManifestSha256 = transactionDict["source"]["manifestSha256"]
    strTargetManifestSha256 = transactionDict["target"]["manifestSha256"]

    if transactionDict["state"] == "prepared":
        if strCurrentManifestSha256 != strSourceManifestSha256:
            raise ComponentManagementError(
                code="project_transaction_recovery_failed",
                message="The Project changed while a prepared dependency transaction was pending.",
                details={"transactionPath": str(transactionPath)},
            )
        return None

    if transactionDict["state"] == "manifestCommitted":
        return _finish_committed_project_transaction(
            projectPath,
            transactionPath,
            transactionDict,
        )

    if strSourceManifestSha256 != strTargetManifestSha256 and strCurrentManifestSha256 == strTargetManifestSha256:
        return _finish_committed_project_transaction(
            projectPath,
            transactionPath,
            transactionDict,
        )

    if strCurrentManifestSha256 not in {None, strSourceManifestSha256}:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="The Project Manifest does not match either side of the interrupted transaction.",
            details={
                "transactionPath": str(transactionPath),
                "actualSha256": strCurrentManifestSha256,
                "sourceSha256": strSourceManifestSha256,
                "targetSha256": strTargetManifestSha256,
            },
        )

    _rollback_project_transaction(
        projectPath,
        transactionPath,
        transactionDict,
    )
    return None


def _cleanup_temporary_transaction_folders(
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
            if folder_invalid(pathEntry):
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


def _recover_project_transactions_locked(
    projectPath: Path,
) -> list[DictComponentManagementWarning]:
    pathTransactions = _get_transactions_path(projectPath)
    if not path_exists(pathTransactions):
        return []

    if folder_invalid(pathTransactions):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The Project transaction path is invalid.",
            details={"transactionsPath": str(pathTransactions)},
        )

    listWarning = _cleanup_temporary_transaction_folders(pathTransactions)
    listTransactionPath = [
        pathEntry
        for pathEntry in sorted(pathTransactions.iterdir(), key=lambda pathObj: pathObj.name)
        if pathEntry.name.startswith(_STR_PROJECT_TRANSACTION_PREFIX)
    ]

    if len(listTransactionPath) > 1:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The Project contains more than one unfinished dependency transaction.",
            details={
                "transactions": [str(pathTransaction) for pathTransaction in listTransactionPath],
            },
        )

    if not listTransactionPath:
        try:
            if not any(pathTransactions.iterdir()):
                pathTransactions.rmdir()
        except OSError:
            pass
        return listWarning

    pathTransaction = listTransactionPath[0]
    if folder_invalid(pathTransaction):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The unfinished Project dependency transaction path is invalid.",
            details={"transactionPath": str(pathTransaction)},
        )

    strTransactionId = pathTransaction.name.removeprefix(_STR_PROJECT_TRANSACTION_PREFIX)
    try:
        transactionUuid = uuid.UUID(strTransactionId)
    except ValueError as e:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The unfinished Project transaction folder name is invalid.",
            details={"transactionPath": str(pathTransaction)},
        ) from e

    if transactionUuid.version != 4 or transactionUuid.variant != uuid.RFC_4122:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The unfinished Project transaction folder must use a UUID v4.",
            details={"transactionPath": str(pathTransaction)},
        )

    dictTransaction = _read_project_transaction(pathTransaction)
    _recover_project_transaction(
        projectPath,
        pathTransaction,
        dictTransaction,
    )

    dictWarning = _remove_transaction_folder(pathTransaction)
    if dictWarning is not None:
        listWarning.append(dictWarning)

    return listWarning


def recover_project_transactions(
    projectPath: Path,
) -> list[DictComponentManagementWarning]:
    """Recover one interrupted Project dependency transaction under the Project lock."""
    pathProject = _resolve_project_path(projectPath)

    with project_lock(
        projectPath=pathProject,
        operation="recoverProjectDependencyTransaction",
    ):
        return _recover_project_transactions_locked(pathProject)


def _read_current_components_lock(
    projectPath: Path,
    manifestObj: ProjectManifest,
    *,
    dependenciesRequired: bool,
) -> DictComponentsLockFile | None:
    if not dependenciesRequired:
        return None

    pathLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    dictLock = read_components_lock(pathLock)
    if is_components_lock_stale(dictLock, manifestObj):
        raise ComponentManagementError(
            code="components_lock_stale",
            message="components.lock.json is stale and must be resolved again.",
            details={"lockFile": str(pathLock)},
        )

    return dictLock


def _validate_confirmed_plan_sha256(value: object) -> str:
    try:
        return validate_sha256(value, "confirmedPlanSha256")
    except ValueError as e:
        raise ComponentManagementError(
            code="dependency_plan_invalid_input",
            message="confirmedPlanSha256 is invalid.",
            details={"reason": str(e)},
        ) from e


def apply_project_dependency_plan(
    projectPath: Path,
    operationObj: ProjectDependencyOperation,
    confirmedPlanSha256: str,
) -> ProjectDependencyApplyResult:
    """Re-resolve and atomically apply a previously confirmed dependency operation plan."""
    pathProject = _resolve_project_path(projectPath)
    strConfirmedPlanSha256 = _validate_confirmed_plan_sha256(confirmedPlanSha256)
    pathRepository = get_repository_path()
    listWarning: list[DictComponentManagementWarning] = []
    planObj: ProjectDependencyPlan
    folderInfo: ComponentsFolderInfo | None

    with repository_lock(
        repositoryPath=pathRepository,
        operation="applyProjectDependencyPlan",
    ):
        listWarning.extend(recover_publish_transactions(pathRepository))
        dictRepositoryIndex = load_repository_index(
            pathRepository,
            checkWheelPaths=True,
        )

        with project_lock(
            projectPath=pathProject,
            operation="applyProjectDependencyPlan",
        ):
            listWarning.extend(_recover_project_transactions_locked(pathProject))
            _, manifestObj = read_project_manifest(pathProject)
            dictCurrentLock = _read_current_components_lock(
                pathProject,
                manifestObj,
                dependenciesRequired=bool(manifestObj.componentDependencies),
            )
            planObj = build_project_dependency_plan(
                manifestObj,
                dictRepositoryIndex,
                operationObj,
                existingLock=dictCurrentLock,
            )

            if planObj.planSha256 != strConfirmedPlanSha256:
                raise ComponentManagementError(
                    code="dependency_plan_changed",
                    message="The dependency plan changed and must be confirmed again.",
                    details={
                        "confirmedPlanSha256": strConfirmedPlanSha256,
                        "currentPlanSha256": planObj.planSha256,
                        "directDependencyChanges": planObj.directDependencyChanges,
                        "resolvedComponentChanges": planObj.resolvedComponentChanges,
                    },
                )

            pathTransaction, dictTransaction = _prepare_project_transaction(
                pathProject,
                pathRepository,
                planObj,
            )
            folderInfo = _commit_project_transaction(
                pathProject,
                pathTransaction,
                dictTransaction,
            )

            dictWarning = _remove_transaction_folder(pathTransaction)
            if dictWarning is not None:
                listWarning.append(dictWarning)

    return ProjectDependencyApplyResult(
        plan=planObj,
        componentsFolderInfo=folderInfo,
        warnings=listWarning,
    )
