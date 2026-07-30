# FileName: _ProjectTransaction.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest
from liberrpa.ComponentManagement.Types._Components import DictComponentsLock_File, Info_ProjectComponentsFolder
from liberrpa.ComponentManagement.Types._Dependency import (
    Info_ProjectDependency_Operation,
    Info_ProjectDependency_Plan,
    Info_ProjectDependency_ApplyResult,
    Info_ProjectDependency_RepairResult,
)
from liberrpa.ComponentManagement.Lock._ProjectLock import project_lock
from liberrpa.ComponentManagement.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement._ProjectTransactionStorage import (
    get_manifest_file,
    remove_transaction_folder,
    prepare_project_transaction,
)
from liberrpa.ComponentManagement._ProjectTransactionLifecycle import (
    commit_project_transaction,
    recover_project_transactions_locked,
)
from liberrpa.ComponentManagement._Components import STR_COMPONENTS_FOLDER_NAME, validate_components_folder
from liberrpa.ComponentManagement._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    is_components_lock_stale,
)
from liberrpa.ComponentManagement._DependencyPlan import build_project_dependency_plan
from liberrpa.ComponentManagement._Manifest import read_project_manifest
from liberrpa.ComponentManagement._Repository import get_repository_path
from liberrpa.ComponentManagement._RepositoryIndex import validate_sha256, load_repository_index
from liberrpa.ComponentManagement._RepositoryTransaction import recover_publish_transactions

from pathlib import Path
from typing import Literal


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


def _validate_source_project_state(
    projectPath: Path,
    planObj: Info_ProjectDependency_Plan,
) -> tuple[Literal["flow", "component"], Literal["flow.json", "component.json"]]:
    strProjectType, currentManifestObj = read_project_manifest(projectPath)
    if currentManifestObj != planObj.sourceManifest:
        raise ComponentManagementError(
            code="dependency_plan_changed",
            message="The Project Manifest changed after the dependency plan was created.",
            details={"planSha256": planObj.planSha256},
        )

    strManifestFile = get_manifest_file(strProjectType)
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


def recover_project_transactions(
    projectPath: Path,
) -> list[DictComponentManagementWarning]:
    """Recover one interrupted Project dependency transaction under the Project lock."""
    pathProject = _resolve_project_path(projectPath)

    with project_lock(
        projectPath=pathProject,
        operation="recoverProjectDependencyTransaction",
    ):
        return recover_project_transactions_locked(pathProject)


def _read_current_components_lock(
    projectPath: Path,
    manifestObj: Info_ProjectManifest,
    *,
    dependenciesRequired: bool,
) -> DictComponentsLock_File | None:
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
    operationObj: Info_ProjectDependency_Operation,
    confirmedPlanSha256: str,
) -> Info_ProjectDependency_ApplyResult:
    """Re-resolve and atomically apply a previously confirmed dependency operation plan."""
    pathProject = _resolve_project_path(projectPath)
    strConfirmedPlanSha256 = _validate_confirmed_plan_sha256(confirmedPlanSha256)
    pathRepository = get_repository_path()
    listWarning: list[DictComponentManagementWarning] = []
    planObj: Info_ProjectDependency_Plan
    folderInfo: Info_ProjectComponentsFolder | None

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
            listWarning.extend(recover_project_transactions_locked(pathProject))
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

            strProjectType, strManifestFile = _validate_source_project_state(
                pathProject,
                planObj,
            )

            pathTransaction, dictTransaction = prepare_project_transaction(
                pathProject,
                pathRepository,
                transactionOperation="applyDependencyPlan",
                projectType=strProjectType,
                manifestFile=strManifestFile,
                sourceManifestObj=planObj.sourceManifest,
                sourceComponentsLock=planObj.sourceComponentsLock,
                targetManifestObj=planObj.targetManifest,
                targetComponentsLock=planObj.targetComponentsLock,
                planSha256=planObj.planSha256,
            )
            folderInfo = commit_project_transaction(
                pathProject,
                pathTransaction,
                dictTransaction,
            )

            dictWarning = remove_transaction_folder(pathTransaction)
            if dictWarning is not None:
                listWarning.append(dictWarning)

    return Info_ProjectDependency_ApplyResult(
        plan=planObj,
        componentsFolderInfo=folderInfo,
        warnings=listWarning,
    )


def repair_project_components(
    projectPath: Path,
) -> Info_ProjectDependency_RepairResult:
    """Rebuild _Components from the current valid lock through a Project transaction."""
    pathProject = _resolve_project_path(projectPath)
    pathRepository = get_repository_path()
    listWarning: list[DictComponentManagementWarning] = []

    with repository_lock(
        repositoryPath=pathRepository,
        operation="repairProjectComponents",
    ):
        listWarning.extend(recover_publish_transactions(pathRepository))

        with project_lock(
            projectPath=pathProject,
            operation="repairProjectComponents",
        ):
            listWarning.extend(recover_project_transactions_locked(pathProject))
            strProjectType, manifestObj = read_project_manifest(pathProject)

            if not manifestObj.componentDependencies:
                raise ComponentManagementError(
                    code="project_components_repair_not_required",
                    message="The Project does not require any Components.",
                    details={"projectPath": str(pathProject)},
                )

            pathLock = pathProject / STR_COMPONENTS_LOCK_FILE_NAME
            dictLock = read_components_lock(pathLock)
            if is_components_lock_stale(dictLock, manifestObj):
                raise ComponentManagementError(
                    code="components_lock_stale",
                    message="components.lock.json is stale and cannot be used to repair _Components.",
                    details={"lockFile": str(pathLock)},
                )

            pathComponents = pathProject / STR_COMPONENTS_FOLDER_NAME
            try:
                validate_components_folder(pathComponents, dictLock)
            except ComponentManagementError as e:
                if e.code not in {"components_folder_missing", "components_folder_damaged"}:
                    raise
            else:
                raise ComponentManagementError(
                    code="project_components_repair_not_required",
                    message="_Components already matches components.lock.json.",
                    details={"componentsPath": str(pathComponents)},
                )

            strManifestFile = get_manifest_file(strProjectType)
            pathTransaction, dictTransaction = prepare_project_transaction(
                pathProject,
                pathRepository,
                transactionOperation="repairProjectComponents",
                projectType=strProjectType,
                manifestFile=strManifestFile,
                sourceManifestObj=manifestObj,
                sourceComponentsLock=dictLock,
                targetManifestObj=manifestObj,
                targetComponentsLock=dictLock,
            )
            folderInfo = commit_project_transaction(
                pathProject,
                pathTransaction,
                dictTransaction,
            )
            assert folderInfo is not None

            dictWarning = remove_transaction_folder(pathTransaction)
            if dictWarning is not None:
                listWarning.append(dictWarning)

    return Info_ProjectDependency_RepairResult(
        componentsFolderInfo=folderInfo,
        warnings=listWarning,
    )
