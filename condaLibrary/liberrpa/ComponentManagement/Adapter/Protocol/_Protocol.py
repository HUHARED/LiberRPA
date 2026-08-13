# FileName: _Protocol.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._DiagnosticLog import DiagnosticLog
from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Types._Protocol import (
    DictProtocolSuccess,
    DictProtocolResponse,
)
from liberrpa.ComponentManagement.Adapter.Protocol._Request import parse_protocol_request
from liberrpa.ComponentManagement.Adapter.Protocol._Response import (
    build_error_response,
    build_publish_response,
    build_component_wheels_imported_response,
    build_repository_index_rebuilt_response,
    build_repository_catalog_response,
    build_project_dependency_state_response,
    build_project_dependency_plan_response,
    build_project_dependency_plan_applied_response,
    build_project_components_repaired_response,
)
from liberrpa.ComponentManagement.Application.Publish._PublishComponent import (
    publish_component,
)
from liberrpa.ComponentManagement.Application.Repository._ImportComponentWheels import (
    import_component_wheels,
)
from liberrpa.ComponentManagement.Application.Repository._RebuildRepositoryIndex import (
    rebuild_repository_index,
)
from liberrpa.ComponentManagement.Application.Repository._RepositorySnapshot import (
    load_repository_catalog_snapshot,
)
from liberrpa.ComponentManagement.Application.Project._DependencyState import (
    get_current_project_dependency_state,
)
from liberrpa.ComponentManagement.Application.Project._DependencyPlan import (
    build_current_project_dependency_plan,
)
from liberrpa.ComponentManagement.Application.Project._ApplyDependencyPlan import (
    apply_project_dependency_plan,
)
from liberrpa.ComponentManagement.Application.Project._RepairComponents import (
    repair_project_components,
)
from liberrpa.ComponentManagement.Domain.Dependency._Plan import (
    parse_project_dependency_operation,
)

from pathlib import Path
from typing import assert_never


def _log_success_response(
    operation: str,
    responseDict: DictProtocolSuccess,
) -> None:
    dictResult: dict[str, object] = dict(responseDict["result"])
    strStatus = str(dictResult["status"])
    intWarningCount = len(responseDict["warnings"])
    DiagnosticLog.info(
        f"Operation completed: {operation} (status={strStatus}, warnings={intWarningCount})."
    )

    dictResultSummary: dict[str, object] = {"status": strStatus}
    for strKey in (
        "planSha256",
        "wheelFileName",
        "sha256",
        "componentCount",
        "versionCount",
        "importedCount",
        "alreadyImportedCount",
        "lockState",
        "componentsState",
        "environmentState",
        "repairState",
    ):
        if strKey in dictResult:
            dictResultSummary[strKey] = dictResult[strKey]

    for strKey in (
        "components",
        "directDependencyChanges",
        "resolvedComponentChanges",
    ):
        value = dictResult.get(strKey)
        if isinstance(value, list):
            dictResultSummary[f"{strKey}Count"] = len(value)

    DiagnosticLog.debug({"resultSummary": dictResultSummary})

    for dictWarning in responseDict["warnings"]:
        DiagnosticLog.warning(dictWarning)


def handle_request(requestInfo: str) -> DictProtocolResponse:
    try:
        dictRequest = parse_protocol_request(requestInfo)
        strOperation = dictRequest["operation"]
        DiagnosticLog.info(f"Operation started: {strOperation}.")
        DiagnosticLog.debug({"request": dictRequest})

        dictResponse: DictProtocolSuccess
        match dictRequest["operation"]:
            case "publishComponent":
                dictResponse = build_publish_response(
                    publish_component(dictRequest["projectPath"])
                )

            case "importComponentWheels":
                importResult = import_component_wheels([
                    Path(strWheelFilePath)
                    for strWheelFilePath in dictRequest["wheelFilePaths"]
                ])
                dictResponse = build_component_wheels_imported_response(importResult)

            case "rebuildRepositoryIndex":
                dictResponse = build_repository_index_rebuilt_response(
                    rebuild_repository_index()
                )

            case "getComponentRepositoryCatalog":
                pathRepository, dictRepositoryIndex, listWarning = (
                    load_repository_catalog_snapshot()
                )
                dictResponse = build_repository_catalog_response(
                    repositoryPath=pathRepository,
                    repositoryIndexDict=dictRepositoryIndex,
                    warningList=listWarning,
                )

            case "getProjectDependencyState":
                stateObj, listWarning = get_current_project_dependency_state(
                    dictRequest["projectPath"]
                )
                dictResponse = build_project_dependency_state_response(
                    stateObj, listWarning
                )

            case "buildProjectDependencyPlan":
                operationObj = parse_project_dependency_operation(
                    dictRequest["dependencyOperation"]
                )
                planObj, listWarning = build_current_project_dependency_plan(
                    dictRequest["projectPath"],
                    operationObj,
                )
                dictResponse = build_project_dependency_plan_response(
                    planObj, listWarning
                )

            case "applyProjectDependencyPlan":
                operationObj = parse_project_dependency_operation(
                    dictRequest["dependencyOperation"]
                )
                applyResult = apply_project_dependency_plan(
                    Path(dictRequest["projectPath"]),
                    operationObj,
                    dictRequest["confirmedPlanSha256"],
                )
                dictResponse = build_project_dependency_plan_applied_response(applyResult)

            case "repairProjectComponents":
                repairResult = repair_project_components(Path(dictRequest["projectPath"]))
                dictResponse = build_project_components_repaired_response(repairResult)

            case _ as operation:
                assert_never(operation)

        _log_success_response(strOperation, dictResponse)
        return dictResponse

    except ComponentManagementError as e:
        DiagnosticLog.error(f"Operation failed [{e.code}]: {e.message}")
        if e.details:
            DiagnosticLog.error(e.details)
        if e.__cause__ is not None:
            DiagnosticLog.debug_exception(
                "Underlying Component Management exception.",
                e.__cause__,
            )
        return build_error_response(e)
