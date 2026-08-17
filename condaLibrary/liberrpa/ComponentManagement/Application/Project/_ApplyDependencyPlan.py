# FileName: _ApplyDependencyPlan.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._DiagnosticLog import DiagnosticLog
from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Components import Info_ProjectComponentsFolder
from liberrpa.ComponentManagement.Types._Dependency import (
    Info_ProjectDependency_Operation,
    Info_ProjectDependency_Plan,
    Info_ProjectDependency_ApplyResult,
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
from liberrpa.ComponentManagement.Domain.Dependency._Plan import (
    build_project_dependency_plan,
)
from liberrpa.ComponentManagement.Application.Project._DependencyPlan import (
    read_current_components_lock_for_operation,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import read_project_manifest
from liberrpa.ComponentManagement.Domain.Repository._Index import (
    validate_sha256,
    load_repository_index,
)
from liberrpa.ComponentManagement.Domain.Repository._RepositoryPath import (
    get_repository_path,
)
from liberrpa.ComponentManagement.Domain.Repository._Transaction import (
    recover_repository_transactions,
)

from pathlib import Path


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
    operationObj: Info_ProjectDependency_Operation,
    confirmedPlanSha256: str,
) -> Info_ProjectDependency_ApplyResult:
    """Re-resolve and atomically apply a previously confirmed dependency operation plan."""
    pathProject = resolve_project_path(projectPath)
    strConfirmedPlanSha256 = _validate_confirmed_plan_sha256(confirmedPlanSha256)
    pathRepository = get_repository_path()
    listWarning: list[DictComponentManagementWarning] = []
    DiagnosticLog.debug({
        "projectPath": str(pathProject),
        "repositoryPath": str(pathRepository),
        "confirmedPlanSha256": strConfirmedPlanSha256,
        "dependencyOperation": operationObj,
    })
    planObj: Info_ProjectDependency_Plan
    folderInfo: Info_ProjectComponentsFolder | None

    with repository_lock(pathRepository, "applyProjectDependencyPlan"):
        listWarning.extend(recover_repository_transactions(pathRepository))

        dictRepositoryIndex = load_repository_index(
            pathRepository,
            checkWheelFilePaths=True,
        )

        with project_lock(pathProject, "applyProjectDependencyPlan"):
            listWarning.extend(recover_project_transactions_locked(pathProject))

            strProjectType, manifestObj = read_project_manifest(pathProject)

            dictCurrentLockFile = read_current_components_lock_for_operation(
                pathProject, manifestObj, operationObj
            )

            planObj = build_project_dependency_plan(
                manifestObj,
                dictRepositoryIndex,
                operationObj,
                existingLockDict=dictCurrentLockFile,
            )
            DiagnosticLog.debug({
                "currentPlanSha256": planObj.planSha256,
                "directDependencyChangeCount": len(planObj.directDependencyChanges),
                "resolvedComponentChangeCount": len(planObj.resolvedComponentChanges),
            })

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

            strManifestFileName = get_manifest_file_name(strProjectType)

            pathTransactionFolder, dictTransaction = prepare_project_transaction(
                pathProject,
                pathRepository,
                transactionOperation="applyDependencyPlan",
                projectType=strProjectType,
                manifestFileName=strManifestFileName,
                sourceManifestObj=planObj.sourceManifest,
                sourceComponentsLockDict=planObj.sourceComponentsLock,
                targetManifestObj=planObj.targetManifest,
                targetComponentsLockDict=planObj.targetComponentsLock,
                planSha256=planObj.planSha256,
            )
            DiagnosticLog.info(
                f"Prepared Project dependency transaction: {pathTransactionFolder}"
            )
            folderInfo = commit_project_transaction(
                pathProject,
                pathTransactionFolder,
                dictTransaction,
            )
            DiagnosticLog.info(
                f"Committed Project dependency transaction: {pathTransactionFolder}"
            )
            if folderInfo is not None:
                DiagnosticLog.debug({
                    "componentsFolderPath": str(folderInfo.componentsFolderPath),
                    "componentCount": folderInfo.componentCount,
                    "fileCount": folderInfo.fileCount,
                })

            dictWarning = remove_transaction_folder(pathTransactionFolder)
            if dictWarning is not None:
                listWarning.append(dictWarning)

    return Info_ProjectDependency_ApplyResult(
        plan=planObj,
        componentsFolderInfo=folderInfo,
        warnings=listWarning,
    )
