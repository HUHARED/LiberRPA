# FileName: _ProjectTransactionLifecycle.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._Validation import (
    path_exists,
    is_folder_invalid,
)
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Components import Info_ProjectComponentsFolder
from liberrpa.ComponentManagement.Types._ProjectTransaction import DictProjectTransaction
from liberrpa.ComponentManagement._ProjectTransactionStorage import (
    STR_TARGET_FOLDER_NAME,
    STR_BACKUP_FOLDER_NAME,
    STR_PROJECT_TRANSACTION_PREFIX,
    get_transactions_path,
    read_project_transaction,
    write_transaction_state,
    remove_transaction_folder,
    get_regular_file_sha256,
    move_source_to_backup,
    move_target_to_project,
    validate_target_project_state,
    restore_source_path,
    ensure_target_path_committed,
    cleanup_temporary_transaction_folders,
)
from liberrpa.ComponentManagement._Components import STR_COMPONENTS_FOLDER_NAME
from liberrpa.ComponentManagement._ComponentsLock import STR_COMPONENTS_LOCK_FILE_NAME

from pathlib import Path
import os
import uuid


def commit_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> Info_ProjectComponentsFolder | None:
    pathTarget = transactionPath / STR_TARGET_FOLDER_NAME
    pathBackup = transactionPath / STR_BACKUP_FOLDER_NAME
    pathManifest = projectPath / transactionDict["manifestFile"]

    try:
        write_transaction_state(
            transactionPath,
            transactionDict,
            "committing",
        )
        move_source_to_backup(
            projectPath,
            pathBackup,
            transactionDict["source"],
        )
        move_target_to_project(
            projectPath,
            pathTarget,
            transactionDict["target"],
        )
        os.replace(
            pathTarget / transactionDict["manifestFile"],
            pathManifest,
        )
        write_transaction_state(
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

    return validate_target_project_state(projectPath, transactionDict)


def _rollback_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> None:
    pathBackup = transactionPath / STR_BACKUP_FOLDER_NAME
    dictSource = transactionDict["source"]

    try:
        restore_source_path(
            projectPath / STR_COMPONENTS_FOLDER_NAME,
            pathBackup / STR_COMPONENTS_FOLDER_NAME,
            sourceExists=dictSource["componentsPathExists"],
        )
        restore_source_path(
            projectPath / STR_COMPONENTS_LOCK_FILE_NAME,
            pathBackup / STR_COMPONENTS_LOCK_FILE_NAME,
            sourceExists=dictSource["componentsLockExists"],
            sourceSha256=dictSource.get("componentsLockSha256"),
        )
        restore_source_path(
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


def _finish_committed_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> Info_ProjectComponentsFolder | None:
    pathTarget = transactionPath / STR_TARGET_FOLDER_NAME
    dictTarget = transactionDict["target"]

    try:
        ensure_target_path_committed(
            projectPath / STR_COMPONENTS_FOLDER_NAME,
            pathTarget / STR_COMPONENTS_FOLDER_NAME,
            targetExists=dictTarget["componentsPathExists"],
        )
        ensure_target_path_committed(
            projectPath / STR_COMPONENTS_LOCK_FILE_NAME,
            pathTarget / STR_COMPONENTS_LOCK_FILE_NAME,
            targetExists=dictTarget["componentsLockExists"],
        )
        ensure_target_path_committed(
            projectPath / transactionDict["manifestFile"],
            pathTarget / transactionDict["manifestFile"],
            targetExists=True,
        )

        folderInfo = validate_target_project_state(projectPath, transactionDict)
        if transactionDict["state"] != "manifestCommitted":
            write_transaction_state(
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

    return get_regular_file_sha256(pathManifest, "Project Manifest")


def _recover_project_transaction(
    projectPath: Path,
    transactionPath: Path,
    transactionDict: DictProjectTransaction,
) -> Info_ProjectComponentsFolder | None:
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


def recover_project_transactions_locked(
    projectPath: Path,
) -> list[DictComponentManagementWarning]:
    pathTransactions = get_transactions_path(projectPath)
    if not path_exists(pathTransactions):
        return []

    if is_folder_invalid(pathTransactions):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The Project transaction path is invalid.",
            details={"transactionsPath": str(pathTransactions)},
        )

    listWarning = cleanup_temporary_transaction_folders(pathTransactions)
    listTransactionPath = [
        pathEntry
        for pathEntry in sorted(pathTransactions.iterdir(), key=lambda pathObj: pathObj.name)
        if pathEntry.name.startswith(STR_PROJECT_TRANSACTION_PREFIX)
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
    if is_folder_invalid(pathTransaction):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The unfinished Project dependency transaction path is invalid.",
            details={"transactionPath": str(pathTransaction)},
        )

    strTransactionId = pathTransaction.name.removeprefix(STR_PROJECT_TRANSACTION_PREFIX)
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

    dictTransaction = read_project_transaction(pathTransaction)
    _recover_project_transaction(
        projectPath,
        pathTransaction,
        dictTransaction,
    )

    dictWarning = remove_transaction_folder(pathTransaction)
    if dictWarning is not None:
        listWarning.append(dictWarning)

    return listWarning
