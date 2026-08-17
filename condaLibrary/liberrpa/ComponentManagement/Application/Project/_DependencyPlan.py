# FileName: _DependencyPlan.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest
from liberrpa.ComponentManagement.Types._Components import DictComponentsLock_File
from liberrpa.ComponentManagement.Types._Dependency import (
    Info_ProjectDependency_Operation_Resolve,
    Info_ProjectDependency_Operation,
    Info_ProjectDependency_Plan,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    is_components_lock_stale,
)
from liberrpa.ComponentManagement.Domain.Dependency._Plan import (
    build_project_dependency_plan,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import read_project_manifest
from liberrpa.ComponentManagement.Application.Project._TransactionRecovery import (
    recover_project_transactions,
)
from liberrpa.ComponentManagement.Application.Repository._RepositorySnapshot import (
    load_repository_resolution_snapshot,
)

from pathlib import Path


def read_current_components_lock_for_operation(
    projectPath: Path,
    manifestObj: Info_ProjectManifest,
    operationObj: Info_ProjectDependency_Operation,
) -> DictComponentsLock_File | None:
    """Read the current lock according to the requested dependency operation."""
    boolDependenciesRequired = bool(manifestObj.componentDependencies)
    if isinstance(operationObj, Info_ProjectDependency_Operation_Resolve):
        if not boolDependenciesRequired:
            raise ComponentManagementError(
                code="dependency_plan_invalid_input",
                message=(
                    "Resolve Project Dependencies requires at least one direct Component dependency."
                ),
            )

        pathComponentsLockFile = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
        try:
            dictLock = read_components_lock(pathComponentsLockFile)
        except ComponentManagementError as e:
            if e.code in {"components_lock_missing", "components_lock_invalid"}:
                return None
            raise

        if not is_components_lock_stale(dictLock, manifestObj):
            raise ComponentManagementError(
                code="dependency_plan_invalid_input",
                message=(
                    "components.lock.json is already valid; dependency resolution is not required."
                ),
                details={"componentsLockFilePath": str(pathComponentsLockFile)},
            )

        # A stale but valid lock can still guide the Resolver to retain compatible versions while its root metadata is regenerated from the current Manifest.
        return dictLock

    if not boolDependenciesRequired:
        return None

    pathComponentsLockFile = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    dictLock = read_components_lock(pathComponentsLockFile)
    if is_components_lock_stale(dictLock, manifestObj):
        raise ComponentManagementError(
            code="components_lock_stale",
            message=(
                "components.lock.json is stale. Resolve Project Dependencies before planning another change."
            ),
            details={"componentsLockFilePath": str(pathComponentsLockFile)},
        )

    return dictLock


def build_current_project_dependency_plan(
    projectPath: str | Path,
    operationObj: Info_ProjectDependency_Operation,
) -> tuple[Info_ProjectDependency_Plan, list[DictComponentManagementWarning]]:
    """Build a dependency plan from the current Project and Repository state."""
    pathProject = resolve_project_path(projectPath)
    dictRepositoryIndex, listRepositoryWarning = load_repository_resolution_snapshot()
    listProjectWarning = recover_project_transactions(pathProject)
    _, manifestObj = read_project_manifest(pathProject)

    dictCurrentLock = read_current_components_lock_for_operation(
        pathProject, manifestObj, operationObj
    )

    planObj = build_project_dependency_plan(
        manifestObj,
        dictRepositoryIndex,
        operationObj,
        existingLockDict=dictCurrentLock,
    )
    return planObj, [*listRepositoryWarning, *listProjectWarning]
