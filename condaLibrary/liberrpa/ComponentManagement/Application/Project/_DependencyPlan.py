# FileName: _DependencyPlan.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Dependency import Info_ProjectDependency_Operation, Info_ProjectDependency_Plan
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    is_components_lock_stale,
)
from liberrpa.ComponentManagement.Domain.Dependency._Plan import build_project_dependency_plan
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import read_project_manifest
from liberrpa.ComponentManagement.Application.Project._TransactionRecovery import recover_project_transactions
from liberrpa.ComponentManagement.Application.Repository._RepositorySnapshot import (
    load_repository_resolution_snapshot,
)

from pathlib import Path


def build_current_project_dependency_plan(
    projectPath: str | Path,
    operationObj: Info_ProjectDependency_Operation,
) -> tuple[Info_ProjectDependency_Plan, list[DictComponentManagementWarning]]:
    """Build a dependency plan from the current Project and Repository state."""
    pathProject = resolve_project_path(projectPath)
    dictRepositoryIndex, listRepositoryWarning = load_repository_resolution_snapshot()
    listProjectWarning = recover_project_transactions(pathProject)
    _, manifestObj = read_project_manifest(pathProject)

    dictCurrentLock = None
    if manifestObj.componentDependencies:
        pathLock = pathProject / STR_COMPONENTS_LOCK_FILE_NAME
        dictCurrentLock = read_components_lock(pathLock)
        if is_components_lock_stale(dictCurrentLock, manifestObj):
            raise ComponentManagementError(
                code="components_lock_stale",
                message="components.lock.json is stale and must be resolved before planning another change.",
                details={"lockFile": str(pathLock)},
            )

    planObj = build_project_dependency_plan(
        manifestObj,
        dictRepositoryIndex,
        operationObj,
        existingLockDict=dictCurrentLock,
    )
    return planObj, [*listRepositoryWarning, *listProjectWarning]
