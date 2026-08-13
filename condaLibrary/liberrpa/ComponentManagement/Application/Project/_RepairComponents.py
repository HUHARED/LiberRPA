# FileName: _RepairComponents.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._DiagnosticLog import DiagnosticLog
from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Dependency import (
    Info_ProjectDependency_RepairResult,
)
from liberrpa.ComponentManagement.Domain.Lock._ProjectLock import project_lock
from liberrpa.ComponentManagement.Domain.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement.Domain.Project._TransactionStorage import (
    get_manifest_file_name,
    remove_transaction_folder,
    prepare_project_transaction,
)
from liberrpa.ComponentManagement.Domain.Project._TransactionLifecycle import (
    commit_project_transaction,
    recover_project_transactions_locked,
)
from liberrpa.ComponentManagement.Domain.Project._Components import (
    STR_COMPONENTS_FOLDER_NAME,
    validate_components_folder,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    is_components_lock_stale,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import read_project_manifest
from liberrpa.ComponentManagement.Domain.Repository._RepositoryPath import (
    get_repository_path,
)
from liberrpa.ComponentManagement.Domain.Repository._Transaction import (
    recover_repository_transactions,
)

from pathlib import Path


def repair_project_components(
    projectPath: Path,
) -> Info_ProjectDependency_RepairResult:
    """Rebuild _Components from the current valid lock through a Project transaction."""
    pathProject = resolve_project_path(projectPath)
    pathRepository = get_repository_path()
    listWarning: list[DictComponentManagementWarning] = []
    DiagnosticLog.debug({
        "projectPath": str(pathProject),
        "repositoryPath": str(pathRepository),
    })

    with repository_lock(pathRepository, "repairProjectComponents"):
        listWarning.extend(recover_repository_transactions(pathRepository))

        with project_lock(pathProject, "repairProjectComponents"):
            listWarning.extend(recover_project_transactions_locked(pathProject))
            strProjectType, manifestObj = read_project_manifest(pathProject)

            if not manifestObj.componentDependencies:
                raise ComponentManagementError(
                    code="project_components_repair_not_required",
                    message="The Project does not require any Components.",
                    details={"projectPath": str(pathProject)},
                )

            pathComponentsLockFile = pathProject / STR_COMPONENTS_LOCK_FILE_NAME
            dictLock = read_components_lock(pathComponentsLockFile)
            if is_components_lock_stale(dictLock, manifestObj):
                raise ComponentManagementError(
                    code="components_lock_stale",
                    message="components.lock.json is stale and cannot be used to repair _Components.",
                    details={"componentsLockFilePath": str(pathComponentsLockFile)},
                )

            pathComponentsFolder = pathProject / STR_COMPONENTS_FOLDER_NAME
            try:
                validate_components_folder(pathComponentsFolder, dictLock)
            except ComponentManagementError as e:
                # Repair is allowed only when _Components is missing or damaged.
                # A valid _Components folder needs no repair, while unrelated validation errors must propagate unchanged.
                if e.code not in {
                    "components_folder_missing",
                    "components_folder_damaged",
                }:
                    raise
            else:
                raise ComponentManagementError(
                    code="project_components_repair_not_required",
                    message="_Components already matches components.lock.json.",
                    details={"componentsFolderPath": str(pathComponentsFolder)},
                )

            DiagnosticLog.info(f"Repairing Project _Components: {pathComponentsFolder}")
            strManifestFileName = get_manifest_file_name(strProjectType)
            pathTransactionFolder, dictTransaction = prepare_project_transaction(
                pathProject,
                pathRepository,
                transactionOperation="repairProjectComponents",
                projectType=strProjectType,
                manifestFileName=strManifestFileName,
                sourceManifestObj=manifestObj,
                sourceComponentsLockDict=dictLock,
                targetManifestObj=manifestObj,
                targetComponentsLockDict=dictLock,
                planSha256=None,
            )
            DiagnosticLog.info(
                f"Prepared Project repair transaction: {pathTransactionFolder}"
            )
            folderInfo = commit_project_transaction(
                pathProject,
                pathTransactionFolder,
                dictTransaction,
            )
            assert folderInfo is not None
            DiagnosticLog.info(
                f"Committed Project repair transaction: {pathTransactionFolder}"
            )
            DiagnosticLog.debug({
                "componentsFolderPath": str(folderInfo.componentsFolderPath),
                "componentCount": folderInfo.componentCount,
                "fileCount": folderInfo.fileCount,
            })

            dictWarning = remove_transaction_folder(pathTransactionFolder)
            if dictWarning is not None:
                listWarning.append(dictWarning)

    return Info_ProjectDependency_RepairResult(
        componentsFolderInfo=folderInfo,
        warnings=listWarning,
    )
