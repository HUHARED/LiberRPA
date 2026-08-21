# FileName: _PackagedFlowProject.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Common._Validation import path_exists
from liberrpa.ComponentManagement.Domain.Dependency._State import (
    get_project_dependency_state,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
)
from liberrpa.ComponentManagement.Domain.Project._Components import (
    STR_COMPONENTS_FOLDER_NAME,
)

from pathlib import Path


def validate_packaged_flow_project(
    projectPath: str | Path,
) -> None:
    pathProject = resolve_project_path(projectPath)
    stateObj = get_project_dependency_state(
        pathProject,
        includeRepairState=False,
    )

    listIssue: list[dict[str, object]] = []
    if stateObj.projectType != "flow":
        listIssue.append({
            "field": "projectType",
            "message": "Only a Flow Project can be installed by Executor.",
        })

    boolDependenciesRequired = bool(stateObj.manifest.componentDependencies)
    if boolDependenciesRequired:
        if stateObj.lockState != "valid":
            listIssue.append({
                "field": STR_COMPONENTS_LOCK_FILE_NAME,
                "message": f"Dependency lock state is {stateObj.lockState}.",
            })
        if stateObj.componentsState != "valid":
            listIssue.append({
                "field": STR_COMPONENTS_FOLDER_NAME,
                "message": f"Component folder state is {stateObj.componentsState}.",
            })
    else:
        pathComponentsLock = pathProject / STR_COMPONENTS_LOCK_FILE_NAME
        pathComponentsFolder = pathProject / STR_COMPONENTS_FOLDER_NAME
        if path_exists(pathComponentsLock):
            listIssue.append({
                "field": STR_COMPONENTS_LOCK_FILE_NAME,
                "message": "The Project does not declare Component dependencies, but components.lock.json exists.",
            })
        if path_exists(pathComponentsFolder):
            listIssue.append({
                "field": STR_COMPONENTS_FOLDER_NAME,
                "message": "The Project does not declare Component dependencies, but _Components exists.",
            })

    if stateObj.environmentState != "compatible":
        listIssue.append({
            "field": "requiresLiberrpa",
            "message": f"Executor environment state is {stateObj.environmentState}.",
        })

    if listIssue:
        raise ComponentManagementError(
            code="packaged_flow_project_invalid",
            message="The packaged Flow Project is not ready for Executor.",
            details={
                "projectPath": str(pathProject),
                "issues": listIssue,
                "dependencyState": {
                    "lockState": stateObj.lockState,
                    "componentsState": stateObj.componentsState,
                    "environmentState": stateObj.environmentState,
                    "details": stateObj.details,
                },
            },
        )
