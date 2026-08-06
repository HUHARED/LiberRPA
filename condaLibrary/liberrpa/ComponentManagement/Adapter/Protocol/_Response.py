# FileName: _Response.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Types._Publish import (
    Info_Publish_PreparationCreated,
    Info_Publish_Published,
    Info_PublishResult,
)
from liberrpa.ComponentManagement.Types._Repository import (
    DictRepository_Index,
    Info_Repository_ImportResult,
    Info_Repository_RebuildResult,
)
from liberrpa.ComponentManagement.Types._Dependency import (
    Info_ProjectDependency_Plan,
    Info_ProjectDependency_ApplyResult,
    Info_ProjectDependency_RepairResult,
    Info_ProjectDependency_State,
)
from liberrpa.ComponentManagement.Types._Components import Info_ProjectComponentsFolder
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Protocol import (
    DictProtocolResult_Publish,
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
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import (
    build_project_manifest_dict,
)

from pathlib import Path
from typing import assert_never


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


def build_error_response(
    errorObj: ComponentManagementError,
) -> DictProtocolResponse_Error:
    return {
        "schemaVersion": 1,
        "ok": False,
        "error": {
            "code": errorObj.code,
            "message": errorObj.message,
            "details": errorObj.details or {},
        },
    }


def build_publish_response(
    publishResult: Info_PublishResult,
) -> DictProtocolSuccess_PublishComponent:
    dictResult: DictProtocolResult_Publish

    if isinstance(publishResult, Info_Publish_PreparationCreated):
        dictResult = {
            "status": publishResult.status,
            "componentId": publishResult.componentId,
            "packageName": publishResult.packageName,
            #
            "astSnippetsFile": publishResult.astSnippetsPath.relative_to(
                publishResult.projectPath
            ).as_posix(),
            "snippetsJsoncFile": publishResult.snippetsConfigPath.relative_to(
                publishResult.projectPath
            ).as_posix(),
            "generatedCount": publishResult.generatedCount,
            "skippedCount": publishResult.skippedCount,
            "warningCount": len(publishResult.warnings),
        }
    elif isinstance(publishResult, Info_Publish_Published):
        dictResult = {
            "status": publishResult.status,
            "componentId": publishResult.componentId,
            "packageName": publishResult.packageName,
            "version": publishResult.version,
            #
            "astSnippetsFile": publishResult.astSnippetsPath.relative_to(
                publishResult.projectPath
            ).as_posix(),
            "snippetsJsoncFile": publishResult.snippetsConfigPath.relative_to(
                publishResult.projectPath
            ).as_posix(),
            "generatedCount": publishResult.generatedCount,
            "skippedCount": publishResult.skippedCount,
            "warningCount": len(publishResult.warnings),
            #
            "excludedCount": publishResult.excludedCount,
            "handWrittenCount": publishResult.handWrittenCount,
            "finalCount": publishResult.finalCount,
            #
            "wheelFileName": publishResult.wheelFileName,
            "sha256": publishResult.sha256,
        }
    else:
        assert_never(publishResult)

    return {
        "schemaVersion": 1,
        "ok": True,
        "result": dictResult,
        "warnings": publishResult.warnings,
    }


def build_component_wheels_imported_response(
    importResult: Info_Repository_ImportResult,
) -> DictProtocolSuccess_ComponentWheelsImported:
    listComponent: list[DictProtocolResult_ComponentWheelsImported_Component] = [
        {
            "sourcePath": str(componentResult.sourcePath),
            "componentId": componentResult.componentId,
            "packageName": componentResult.packageName,
            "version": componentResult.version,
            "wheelFileName": componentResult.wheelFileName,
            "sha256": componentResult.sha256,
            "status": componentResult.status,
        }
        for componentResult in importResult.components
    ]
    dictResult: DictProtocolResult_ComponentWheelsImported = {
        "status": "componentWheelsImported",
        "importedCount": sum(
            componentResult["status"] == "imported" for componentResult in listComponent
        ),
        "alreadyImportedCount": sum(
            componentResult["status"] == "alreadyImported"
            for componentResult in listComponent
        ),
        "components": listComponent,
    }
    return {
        "schemaVersion": 1,
        "ok": True,
        "result": dictResult,
        "warnings": importResult.warnings,
    }


def build_repository_index_rebuilt_response(
    rebuildResult: Info_Repository_RebuildResult,
) -> DictProtocolSuccess_RepositoryIndexRebuilt:
    dictResult: DictProtocolResult_RepositoryIndexRebuilt = {
        "status": "repositoryIndexRebuilt",
        "componentCount": rebuildResult.componentCount,
        "versionCount": rebuildResult.versionCount,
    }
    return {
        "schemaVersion": 1,
        "ok": True,
        "result": dictResult,
        "warnings": rebuildResult.warnings,
    }


def build_repository_catalog_response(
    repositoryPath: Path,
    repositoryIndex: DictRepository_Index,
    warningList: list[DictComponentManagementWarning],
) -> DictProtocolSuccess_RepositoryCatalog:
    listComponent: list[DictProtocolResult_RepositoryCatalog_Component] = [
        {
            "componentId": strComponentId,
            "packageName": dictComponent["packageName"],
            "versions": list(reversed(dictComponent["versions"])),
        }
        for strComponentId, dictComponent in sorted(
            repositoryIndex["components"].items(),
            key=lambda item: (item[1]["packageName"].casefold(), item[0]),
        )
    ]
    dictResult: DictProtocolResult_RepositoryCatalog = {
        "status": "componentRepositoryCatalog",
        "repositoryPath": str(repositoryPath),
        "componentCount": len(listComponent),
        "versionCount": sum(
            len(dictComponent["versions"]) for dictComponent in listComponent
        ),
        "components": listComponent,
    }
    return {
        "schemaVersion": 1,
        "ok": True,
        "result": dictResult,
        "warnings": warningList,
    }


def build_project_dependency_state_response(
    stateObj: Info_ProjectDependency_State,
    warningList: list[DictComponentManagementWarning],
) -> DictProtocolSuccess_ProjectDependencyState:
    dictResult: DictProtocolResult_ProjectDependencyState = {
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
    return {
        "schemaVersion": 1,
        "ok": True,
        "result": dictResult,
        "warnings": warningList,
    }


def build_project_dependency_plan_response(
    planObj: Info_ProjectDependency_Plan,
    warningList: list[DictComponentManagementWarning],
) -> DictProtocolSuccess_ProjectDependencyPlan:
    return {
        "schemaVersion": 1,
        "ok": True,
        "result": _get_project_dependency_plan_result(planObj),
        "warnings": warningList,
    }


def build_project_dependency_plan_applied_response(
    applyResult: Info_ProjectDependency_ApplyResult,
) -> DictProtocolSuccess_ProjectDependencyPlanApplied:
    folderResult = (
        None
        if applyResult.componentsFolderInfo is None
        else _get_components_folder_result(applyResult.componentsFolderInfo)
    )
    dictResult: DictProtocolResult_ProjectDependencyPlanApplied = {
        "status": "projectDependencyPlanApplied",
        "planSha256": applyResult.plan.planSha256,
        "targetManifest": build_project_manifest_dict(applyResult.plan.targetManifest),
        "targetComponentsLock": applyResult.plan.targetComponentsLock,
        "directDependencyChanges": applyResult.plan.directDependencyChanges,
        "resolvedComponentChanges": applyResult.plan.resolvedComponentChanges,
        "componentsFolder": folderResult,
    }
    return {
        "schemaVersion": 1,
        "ok": True,
        "result": dictResult,
        "warnings": applyResult.warnings,
    }


def build_project_components_repaired_response(
    repairResult: Info_ProjectDependency_RepairResult,
) -> DictProtocolSuccess_ProjectComponentsRepaired:
    dictResult: DictProtocolResult_ProjectComponentsRepaired = {
        "status": "projectComponentsRepaired",
        "componentsFolder": _get_components_folder_result(
            repairResult.componentsFolderInfo
        ),
    }
    return {
        "schemaVersion": 1,
        "ok": True,
        "result": dictResult,
        "warnings": repairResult.warnings,
    }
