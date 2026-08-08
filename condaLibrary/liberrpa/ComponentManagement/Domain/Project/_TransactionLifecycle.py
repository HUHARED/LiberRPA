# FileName: _TransactionLifecycle.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Validation import (
    path_exists,
    is_folder_invalid,
)
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Components import Info_ProjectComponentsFolder
from liberrpa.ComponentManagement.Types._ProjectTransaction import DictProjectTransaction
from liberrpa.ComponentManagement.Domain.Project._TransactionStorage import (
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
    restore_source_entry,
    ensure_target_entry_committed,
    cleanup_temporary_transaction_folders,
)
from liberrpa.ComponentManagement.Domain.Project._Components import (
    STR_COMPONENTS_FOLDER_NAME,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
)

from pathlib import Path
import os
import uuid


def commit_project_transaction(
    projectPath: Path,
    transactionFolderPath: Path,
    transactionDict: DictProjectTransaction,
) -> Info_ProjectComponentsFolder | None:
    pathTargetFolder = transactionFolderPath / STR_TARGET_FOLDER_NAME
    pathBackupFolder = transactionFolderPath / STR_BACKUP_FOLDER_NAME
    pathManifestFile = projectPath / transactionDict["manifestFileName"]

    try:
        write_transaction_state(
            transactionFolderPath,
            transactionDict,
            "committing",
        )
        move_source_to_backup(
            projectPath,
            pathBackupFolder,
            transactionDict["source"],
        )
        move_target_to_project(
            projectPath,
            pathTargetFolder,
            transactionDict["target"],
        )
        os.replace(
            pathTargetFolder / transactionDict["manifestFileName"],
            pathManifestFile,
        )
        write_transaction_state(
            transactionFolderPath,
            transactionDict,
            "manifestCommitted",
        )
    except ComponentManagementError:
        raise
    except OSError as e:
        raise ComponentManagementError(
            code="project_transaction_failed",
            message="Failed to commit the Project dependency transaction.",
            details={"transactionFolderPath": str(transactionFolderPath)},
        ) from e

    return validate_target_project_state(projectPath, transactionDict)


def _rollback_project_transaction(
    projectPath: Path,
    transactionFolderPath: Path,
    transactionDict: DictProjectTransaction,
) -> None:
    pathBackupFolder = transactionFolderPath / STR_BACKUP_FOLDER_NAME
    dictSourceSnapshot = transactionDict["source"]

    try:
        restore_source_entry(
            projectPath / STR_COMPONENTS_FOLDER_NAME,
            pathBackupFolder / STR_COMPONENTS_FOLDER_NAME,
            sourceShouldExist=dictSourceSnapshot["componentsFolderShouldExist"],
            expectedSourceSha256=None,
        )
        restore_source_entry(
            projectPath / STR_COMPONENTS_LOCK_FILE_NAME,
            pathBackupFolder / STR_COMPONENTS_LOCK_FILE_NAME,
            sourceShouldExist=dictSourceSnapshot["componentsLockFileShouldExist"],
            expectedSourceSha256=dictSourceSnapshot.get(
                "expectedComponentsLockFileSha256"
            ),
        )
        restore_source_entry(
            projectPath / transactionDict["manifestFileName"],
            pathBackupFolder / transactionDict["manifestFileName"],
            sourceShouldExist=True,
            expectedSourceSha256=dictSourceSnapshot["manifestSha256"],
        )
    except (ComponentManagementError, OSError) as e:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="Failed to roll back an interrupted Project dependency transaction.",
            details={
                "transactionFolderPath": str(transactionFolderPath),
                "reason": str(e),
            },
        ) from e


def _finish_committed_project_transaction(
    projectPath: Path,
    transactionFolderPath: Path,
    transactionDict: DictProjectTransaction,
) -> Info_ProjectComponentsFolder | None:
    pathTargetFolder = transactionFolderPath / STR_TARGET_FOLDER_NAME
    dictTarget = transactionDict["target"]

    try:
        ensure_target_entry_committed(
            projectPath / STR_COMPONENTS_FOLDER_NAME,
            pathTargetFolder / STR_COMPONENTS_FOLDER_NAME,
            targetShouldExist=dictTarget["componentsFolderShouldExist"],
        )
        ensure_target_entry_committed(
            projectPath / STR_COMPONENTS_LOCK_FILE_NAME,
            pathTargetFolder / STR_COMPONENTS_LOCK_FILE_NAME,
            targetShouldExist=dictTarget["componentsLockFileShouldExist"],
        )
        ensure_target_entry_committed(
            projectPath / transactionDict["manifestFileName"],
            pathTargetFolder / transactionDict["manifestFileName"],
            targetShouldExist=True,
        )

        folderInfo = validate_target_project_state(projectPath, transactionDict)
        if transactionDict["state"] != "manifestCommitted":
            write_transaction_state(
                transactionFolderPath,
                transactionDict,
                "manifestCommitted",
            )
        return folderInfo
    except (ComponentManagementError, OSError) as e:
        if (
            isinstance(e, ComponentManagementError)
            and e.code == "project_transaction_recovery_failed"
        ):
            raise

        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="Failed to finish an interrupted committed Project dependency transaction.",
            details={
                "transactionFolderPath": str(transactionFolderPath),
                "reason": str(e),
            },
        ) from e


def _get_current_manifest_sha256(
    projectPath: Path,
    manifestFileName: str,
) -> str | None:
    pathManifestFile = projectPath / manifestFileName
    if not path_exists(pathManifestFile):
        return None

    return get_regular_file_sha256(pathManifestFile, "Project Manifest")


def _recover_project_transaction(
    projectPath: Path,
    transactionFolderPath: Path,
    transactionDict: DictProjectTransaction,
) -> Info_ProjectComponentsFolder | None:
    strCurrentManifestSha256 = _get_current_manifest_sha256(
        projectPath,
        transactionDict["manifestFileName"],
    )
    strSourceManifestSha256 = transactionDict["source"]["manifestSha256"]
    strTargetManifestSha256 = transactionDict["target"]["manifestSha256"]

    # A prepared transaction has not started modifying the Project yet.
    # The current Manifest must therefore still match the source snapshot.
    # If it does, the transaction can be discarded without rollback.
    if transactionDict["state"] == "prepared":
        if strCurrentManifestSha256 != strSourceManifestSha256:
            raise ComponentManagementError(
                code="project_transaction_recovery_failed",
                message="The Project changed while a prepared dependency transaction was pending.",
                details={"transactionFolderPath": str(transactionFolderPath)},
            )
        return None

    # The Manifest was committed and the transaction state was persisted successfully.
    # Finish forward recovery and make the remaining Project entries match the target snapshot.
    if transactionDict["state"] == "manifestCommitted":
        return _finish_committed_project_transaction(
            projectPath,
            transactionFolderPath,
            transactionDict,
        )

    # transactionDict["state"] == "commiting"
    # The target Manifest may have been committed immediately before the process was interrupted, leaving the transaction state at "committing". When the source and target Manifests differ, the target Manifest SHA-256 is sufficient evidence that the transaction crossed its final commit point, so finish forward recovery.
    # This inference cannot be used for Repair because its source and target Manifests are intentionally identical.
    if (
        strSourceManifestSha256 != strTargetManifestSha256
        and strCurrentManifestSha256 == strTargetManifestSha256
    ):
        return _finish_committed_project_transaction(
            projectPath,
            transactionFolderPath,
            transactionDict,
        )

    # No forward-commit evidence was found. At this point the current Manifest may only be missing or still match the source snapshot. Any third Manifest state is ambiguous and must not be overwritten automatically.
    if strCurrentManifestSha256 not in {None, strSourceManifestSha256}:
        raise ComponentManagementError(
            code="project_transaction_recovery_failed",
            message="The Project Manifest does not match either side of the interrupted transaction.",
            details={
                "transactionFolderPath": str(transactionFolderPath),
                "actualSha256": strCurrentManifestSha256,
                "sourceSha256": strSourceManifestSha256,
                "targetSha256": strTargetManifestSha256,
            },
        )

    # The final Manifest commit cannot be proven. Roll back conservatively to the source snapshot. A missing Manifest can still be restored from the transaction backup when available.
    _rollback_project_transaction(
        projectPath,
        transactionFolderPath,
        transactionDict,
    )
    return None


def recover_project_transactions_locked(
    projectPath: Path,
) -> list[DictComponentManagementWarning]:
    pathTransactionsFolder = get_transactions_path(projectPath)
    if not path_exists(pathTransactionsFolder):
        return []

    if is_folder_invalid(pathTransactionsFolder):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The Project transaction path is invalid.",
            details={"transactionsPath": str(pathTransactionsFolder)},
        )

    listWarning = cleanup_temporary_transaction_folders(pathTransactionsFolder)

    listSpecificTransactionPath = [
        pathEntry
        for pathEntry in sorted(
            pathTransactionsFolder.iterdir(), key=lambda pathObj: pathObj.name
        )
        if pathEntry.name.startswith(STR_PROJECT_TRANSACTION_PREFIX)
    ]

    if len(listSpecificTransactionPath) > 1:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The Project contains more than one unfinished dependency transaction.",
            details={
                "transactions": [
                    str(pathTransaction)
                    for pathTransaction in listSpecificTransactionPath
                ],
            },
        )

    if not listSpecificTransactionPath:
        try:
            if not any(pathTransactionsFolder.iterdir()):
                pathTransactionsFolder.rmdir()
        except OSError:
            pass
        return listWarning

    pathSpecificTransactionFolder = listSpecificTransactionPath[0]
    if is_folder_invalid(pathSpecificTransactionFolder):
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The unfinished Project dependency transaction path is invalid.",
            details={"transactionFolderPath": str(pathSpecificTransactionFolder)},
        )

    strTransactionId = pathSpecificTransactionFolder.name.removeprefix(
        STR_PROJECT_TRANSACTION_PREFIX
    )
    try:
        transactionUuid = uuid.UUID(strTransactionId)
    except ValueError as e:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The unfinished Project transaction folder name is invalid.",
            details={"transactionFolderPath": str(pathSpecificTransactionFolder)},
        ) from e

    if transactionUuid.version != 4 or transactionUuid.variant != uuid.RFC_4122:
        raise ComponentManagementError(
            code="project_transaction_invalid",
            message="The unfinished Project transaction folder must use a UUID v4.",
            details={"transactionFolderPath": str(pathSpecificTransactionFolder)},
        )

    dictTransaction = read_project_transaction(pathSpecificTransactionFolder)
    _recover_project_transaction(
        projectPath,
        pathSpecificTransactionFolder,
        dictTransaction,
    )

    dictWarning = remove_transaction_folder(pathSpecificTransactionFolder)
    if dictWarning is not None:
        listWarning.append(dictWarning)

    return listWarning
