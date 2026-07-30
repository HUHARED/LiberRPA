# FileName: _Protocol.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import parse_json
from liberrpa.ComponentManagement.Utils._Validation import validate_exact_keys
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Components import Info_ProjectComponentsFolder
from liberrpa.ComponentManagement.Types._Dependency import Info_ProjectDependency_Plan
from liberrpa.ComponentManagement.Types._Protocol import (
    DictProtocolRequest_PublishComponent,
    DictProtocolRequest_RebuildRepositoryIndex,
    DictProtocolRequest_ImportComponentWheels,
    DictProtocolRequest_GetComponentRepositoryCatalog,
    DictProtocolRequest_GetProjectDependencyState,
    DictProtocolRequest_BuildProjectDependencyPlan,
    DictProtocolRequest_ApplyProjectDependencyPlan,
    DictProtocolRequest_RepairProjectComponents,
    DictProtocolRequest,
    DictProtocolResult_RepositoryIndexRebuilt,
    DictProtocolResult_ComponentWheelsImported_Component,
    DictProtocolResult_ComponentWheelsImported,
    DictProtocolResult_RepositoryCatalog_Component,
    DictProtocolResult_RepositoryCatalog,
    DictProtocolResult_ComponentsFolder,
    DictProtocolResult_ProjectDependencyState,
    DictProtocolResult_ProjectDependencyPlan,
    DictProtocolResult_ProjectDependencyPlanApplied,
    DictProtocolResult_ProjectComponentsRepaired,
    DictProtocolSuccess_PublishComponent,
    DictProtocolSuccess_RepositoryIndexRebuilt,
    DictProtocolSuccess_ComponentWheelsImported,
    DictProtocolSuccess_RepositoryCatalog,
    DictProtocolSuccess_ProjectDependencyState,
    DictProtocolSuccess_ProjectDependencyPlan,
    DictProtocolSuccess_ProjectDependencyPlanApplied,
    DictProtocolSuccess_ProjectComponentsRepaired,
    DictProtocolResponse_Error,
    DictProtocolResponse,
)
from liberrpa.ComponentManagement._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    is_components_lock_stale,
)
from liberrpa.ComponentManagement._DependencyPlan import (
    parse_project_dependency_operation,
    build_project_dependency_plan,
)
from liberrpa.ComponentManagement._Manifest import build_project_manifest_dict, read_project_manifest
from liberrpa.ComponentManagement._ProjectDependencyState import get_project_dependency_state
from liberrpa.ComponentManagement._ProjectTransaction import (
    recover_project_transactions,
    apply_project_dependency_plan,
    repair_project_components,
)
from liberrpa.ComponentManagement._Publish import publish_component
from liberrpa.ComponentManagement._Repository import (
    load_repository_resolution_snapshot,
    load_repository_catalog_snapshot,
    rebuild_repository_index,
)
from liberrpa.ComponentManagement._RepositoryImport import import_component_wheels

from pathlib import Path
from typing import NoReturn, cast


_SET_PUBLISH_REQUEST_KEYS = {"schemaVersion", "operation", "projectPath"}
_SET_REBUILD_REQUEST_KEYS = {"schemaVersion", "operation"}
_SET_IMPORT_WHEELS_REQUEST_KEYS = {"schemaVersion", "operation", "wheelPaths"}
_SET_GET_REPOSITORY_CATALOG_REQUEST_KEYS = {"schemaVersion", "operation"}
_SET_GET_STATE_REQUEST_KEYS = {"schemaVersion", "operation", "projectPath"}
_SET_BUILD_PLAN_REQUEST_KEYS = {
    "schemaVersion",
    "operation",
    "projectPath",
    "dependencyOperation",
}
_SET_APPLY_PLAN_REQUEST_KEYS = {
    "schemaVersion",
    "operation",
    "projectPath",
    "dependencyOperation",
    "confirmedPlanSha256",
}
_SET_REPAIR_REQUEST_KEYS = {"schemaVersion", "operation", "projectPath"}


def _raise_invalid_request(
    message: str,
    details: dict[str, object] | None = None,
) -> NoReturn:
    raise ComponentManagementError(
        code="invalid_request",
        message=message,
        details=details,
    )


def _validate_request_keys(
    value: dict[object, object],
    expectedKeys: set[str],
    operationName: str,
) -> None:
    try:
        validate_exact_keys(value, expectedKeys, "request")
    except ValueError as e:
        _raise_invalid_request(
            f"{operationName} request contains missing or unknown fields.",
            {"reason": str(e)},
        )


def _validate_project_path_value(value: object) -> str:
    if not isinstance(value, str) or value.strip() == "":
        _raise_invalid_request("projectPath must be a non-empty string.")
    return value


def _parse_request(requestInfo: str) -> DictProtocolRequest:
    if requestInfo.strip() == "":
        _raise_invalid_request("Component Management request cannot be empty.")

    try:
        value = parse_json(requestInfo)
    except ValueError as e:
        _raise_invalid_request(
            "Component Management request must be valid JSON.",
            {"reason": str(e)},
        )

    if not isinstance(value, dict):
        _raise_invalid_request("Component Management request root must be an object.")

    if type(value.get("schemaVersion")) is not int or value.get("schemaVersion") != 1:
        _raise_invalid_request("Only Component Management protocol schemaVersion 1 is supported.")

    operation = value.get("operation")
    match operation:
        case "publishComponent":
            _validate_request_keys(value, _SET_PUBLISH_REQUEST_KEYS, "Publish Component")
            _validate_project_path_value(value.get("projectPath"))
            return cast(DictProtocolRequest_PublishComponent, value)

        case "rebuildRepositoryIndex":
            _validate_request_keys(value, _SET_REBUILD_REQUEST_KEYS, "Rebuild Repository Index")
            return cast(DictProtocolRequest_RebuildRepositoryIndex, value)

        case "importComponentWheels":
            _validate_request_keys(value, _SET_IMPORT_WHEELS_REQUEST_KEYS, "Import Component Wheels")
            wheelPaths = value.get("wheelPaths")
            if not isinstance(wheelPaths, list) or not wheelPaths:
                _raise_invalid_request("wheelPaths must be a non-empty array of strings.")
            if any(not isinstance(wheelPath, str) or wheelPath.strip() == "" for wheelPath in wheelPaths):
                _raise_invalid_request("wheelPaths must be a non-empty array of strings.")
            return cast(DictProtocolRequest_ImportComponentWheels, value)

        case "getComponentRepositoryCatalog":
            _validate_request_keys(
                value,
                _SET_GET_REPOSITORY_CATALOG_REQUEST_KEYS,
                "Get Component Repository Catalog",
            )
            return cast(DictProtocolRequest_GetComponentRepositoryCatalog, value)

        case "getProjectDependencyState":
            _validate_request_keys(value, _SET_GET_STATE_REQUEST_KEYS, "Get Project Dependency State")
            _validate_project_path_value(value.get("projectPath"))
            return cast(DictProtocolRequest_GetProjectDependencyState, value)

        case "buildProjectDependencyPlan":
            _validate_request_keys(value, _SET_BUILD_PLAN_REQUEST_KEYS, "Build Project Dependency Plan")
            _validate_project_path_value(value.get("projectPath"))
            if not isinstance(value.get("dependencyOperation"), dict):
                _raise_invalid_request("dependencyOperation must be an object.")
            return cast(DictProtocolRequest_BuildProjectDependencyPlan, value)

        case "applyProjectDependencyPlan":
            _validate_request_keys(value, _SET_APPLY_PLAN_REQUEST_KEYS, "Apply Project Dependency Plan")
            _validate_project_path_value(value.get("projectPath"))
            if not isinstance(value.get("dependencyOperation"), dict):
                _raise_invalid_request("dependencyOperation must be an object.")
            if not isinstance(value.get("confirmedPlanSha256"), str):
                _raise_invalid_request("confirmedPlanSha256 must be a string.")
            return cast(DictProtocolRequest_ApplyProjectDependencyPlan, value)

        case "repairProjectComponents":
            _validate_request_keys(value, _SET_REPAIR_REQUEST_KEYS, "Repair Project Components")
            _validate_project_path_value(value.get("projectPath"))
            return cast(DictProtocolRequest_RepairProjectComponents, value)

        case _:
            _raise_invalid_request(
                f"Unsupported Component Management operation: {operation!r}.",
            )


def _resolve_project_path(projectPathValue: str) -> Path:
    try:
        pathProject = Path(projectPathValue).expanduser().resolve()
    except (OSError, RuntimeError) as e:
        raise ComponentManagementError(
            code="project_path_invalid",
            message=f"Failed to resolve the Project path: {projectPathValue}",
        ) from e

    if not pathProject.is_dir():
        raise ComponentManagementError(
            code="project_path_invalid",
            message=f"Project folder was not found: {pathProject}",
        )

    return pathProject


def _get_components_folder_result(
    folderInfo: Info_ProjectComponentsFolder,
) -> DictProtocolResult_ComponentsFolder:
    return {
        "componentsPath": str(folderInfo.componentsPath),
        "componentCount": folderInfo.componentCount,
        "fileCount": folderInfo.fileCount,
    }


def _get_project_dependency_plan_result(
    planObj: Info_ProjectDependency_Plan,
) -> DictProtocolResult_ProjectDependencyPlan:
    return {
        "status": "projectDependencyPlanCreated",
        "planSha256": planObj.planSha256,
        "sourceManifest": build_project_manifest_dict(planObj.sourceManifest),
        "sourceComponentsLock": planObj.sourceComponentsLock,
        "targetManifest": build_project_manifest_dict(planObj.targetManifest),
        "targetComponentsLock": planObj.targetComponentsLock,
        "directDependencyChanges": planObj.directDependencyChanges,
        "resolvedComponentChanges": planObj.resolvedComponentChanges,
    }


def _build_project_dependency_plan_from_request(
    requestObj: DictProtocolRequest_BuildProjectDependencyPlan,
) -> tuple[Info_ProjectDependency_Plan, list[DictComponentManagementWarning]]:
    pathProject = _resolve_project_path(requestObj["projectPath"])
    operationObj = parse_project_dependency_operation(requestObj["dependencyOperation"])
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
        existingLock=dictCurrentLock,
    )
    return planObj, [*listRepositoryWarning, *listProjectWarning]


def _build_error_response(errorObj: ComponentManagementError) -> DictProtocolResponse_Error:
    return {
        "schemaVersion": 1,
        "ok": False,
        "error": {
            "code": errorObj.code,
            "message": errorObj.message,
            "details": errorObj.details or {},
        },
    }


def handle_request(requestInfo: str) -> DictProtocolResponse:
    try:
        dictRequest = _parse_request(requestInfo)

        match dictRequest["operation"]:
            case "publishComponent":
                publishResult, listWarning = publish_component(dictRequest["projectPath"])

                responsePublish: DictProtocolSuccess_PublishComponent = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": publishResult,
                    "warnings": listWarning,
                }
                return responsePublish

            case "rebuildRepositoryIndex":
                rebuildResult = rebuild_repository_index()
                dictRebuildResult: DictProtocolResult_RepositoryIndexRebuilt = {
                    "status": "repositoryIndexRebuilt",
                    "componentCount": rebuildResult.componentCount,
                    "versionCount": rebuildResult.versionCount,
                }
                responseRebuilt: DictProtocolSuccess_RepositoryIndexRebuilt = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": dictRebuildResult,
                    "warnings": rebuildResult.warnings,
                }
                return responseRebuilt

            case "importComponentWheels":
                importResult = import_component_wheels([
                    Path(strWheelPath) for strWheelPath in dictRequest["wheelPaths"]
                ])
                listImportedComponent: list[DictProtocolResult_ComponentWheelsImported_Component] = [
                    {
                        "sourcePath": str(componentResult.sourcePath),
                        "componentId": componentResult.componentId,
                        "packageName": componentResult.packageName,
                        "version": componentResult.version,
                        "wheelFile": componentResult.wheelFile,
                        "sha256": componentResult.sha256,
                        "status": componentResult.status,
                    }
                    for componentResult in importResult.components
                ]
                dictImportResult: DictProtocolResult_ComponentWheelsImported = {
                    "status": "componentWheelsImported",
                    "importedCount": sum(
                        componentResult["status"] == "imported" for componentResult in listImportedComponent
                    ),
                    "alreadyImportedCount": sum(
                        componentResult["status"] == "alreadyImported" for componentResult in listImportedComponent
                    ),
                    "components": listImportedComponent,
                }
                responseImported: DictProtocolSuccess_ComponentWheelsImported = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": dictImportResult,
                    "warnings": importResult.warnings,
                }
                return responseImported

            case "getComponentRepositoryCatalog":
                pathRepository, dictRepositoryIndex, listWarning = load_repository_catalog_snapshot()
                listComponent: list[DictProtocolResult_RepositoryCatalog_Component] = [
                    {
                        "componentId": strComponentId,
                        "packageName": dictComponent["packageName"],
                        "versions": list(reversed(dictComponent["versions"])),
                    }
                    for strComponentId, dictComponent in sorted(
                        dictRepositoryIndex["components"].items(),
                        key=lambda item: (item[1]["packageName"].casefold(), item[0]),
                    )
                ]
                dictCatalogResult: DictProtocolResult_RepositoryCatalog = {
                    "status": "componentRepositoryCatalog",
                    "repositoryPath": str(pathRepository),
                    "componentCount": len(listComponent),
                    "versionCount": sum(
                        len(dictCatalogComponent["versions"]) for dictCatalogComponent in listComponent
                    ),
                    "components": listComponent,
                }
                responseCatalog: DictProtocolSuccess_RepositoryCatalog = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": dictCatalogResult,
                    "warnings": listWarning,
                }
                return responseCatalog

            case "getProjectDependencyState":
                pathProject = _resolve_project_path(dictRequest["projectPath"])
                listWarning = recover_project_transactions(pathProject)
                stateObj = get_project_dependency_state(pathProject)
                dictStateResult: DictProtocolResult_ProjectDependencyState = {
                    "status": "projectDependencyState",
                    "projectPath": str(stateObj.projectPath),
                    "projectType": stateObj.projectType,
                    "manifest": build_project_manifest_dict(stateObj.manifest),
                    "componentsLock": stateObj.componentsLock,
                    "lockState": stateObj.lockState,
                    "componentsState": stateObj.componentsState,
                    "environmentState": stateObj.environmentState,
                    "repairState": stateObj.repairState,
                    "details": stateObj.details,
                }
                responseState: DictProtocolSuccess_ProjectDependencyState = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": dictStateResult,
                    "warnings": listWarning,
                }
                return responseState

            case "buildProjectDependencyPlan":
                planObj, listWarning = _build_project_dependency_plan_from_request(dictRequest)
                responsePlan: DictProtocolSuccess_ProjectDependencyPlan = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": _get_project_dependency_plan_result(planObj),
                    "warnings": listWarning,
                }
                return responsePlan

            case "applyProjectDependencyPlan":
                operationObj = parse_project_dependency_operation(dictRequest["dependencyOperation"])
                applyResult = apply_project_dependency_plan(
                    Path(dictRequest["projectPath"]),
                    operationObj,
                    dictRequest["confirmedPlanSha256"],
                )
                folderResult = (
                    None
                    if applyResult.componentsFolderInfo is None
                    else _get_components_folder_result(applyResult.componentsFolderInfo)
                )
                dictAppliedResult: DictProtocolResult_ProjectDependencyPlanApplied = {
                    "status": "projectDependencyPlanApplied",
                    "planSha256": applyResult.plan.planSha256,
                    "targetManifest": build_project_manifest_dict(applyResult.plan.targetManifest),
                    "targetComponentsLock": applyResult.plan.targetComponentsLock,
                    "directDependencyChanges": applyResult.plan.directDependencyChanges,
                    "resolvedComponentChanges": applyResult.plan.resolvedComponentChanges,
                    "componentsFolder": folderResult,
                }
                responseApplied: DictProtocolSuccess_ProjectDependencyPlanApplied = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": dictAppliedResult,
                    "warnings": applyResult.warnings,
                }
                return responseApplied

            case "repairProjectComponents":
                repairResult = repair_project_components(Path(dictRequest["projectPath"]))
                dictRepairResult: DictProtocolResult_ProjectComponentsRepaired = {
                    "status": "projectComponentsRepaired",
                    "componentsFolder": _get_components_folder_result(
                        repairResult.componentsFolderInfo,
                    ),
                }
                responseRepair: DictProtocolSuccess_ProjectComponentsRepaired = {
                    "schemaVersion": 1,
                    "ok": True,
                    "result": dictRepairResult,
                    "warnings": repairResult.warnings,
                }
                return responseRepair

    except ComponentManagementError as e:
        return _build_error_response(e)
