# FileName: _Protocol.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Types._Protocol import DictProtocolResponse
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
from liberrpa.ComponentManagement.Application.Publish._PublishComponent import publish_component
from liberrpa.ComponentManagement.Application.Repository._ImportComponentWheels import import_component_wheels
from liberrpa.ComponentManagement.Application.Repository._RebuildRepositoryIndex import rebuild_repository_index
from liberrpa.ComponentManagement.Application.Repository._RepositorySnapshot import load_repository_catalog_snapshot
from liberrpa.ComponentManagement.Application.Project._DependencyState import get_current_project_dependency_state
from liberrpa.ComponentManagement.Application.Project._DependencyPlan import build_current_project_dependency_plan
from liberrpa.ComponentManagement.Application.Project._ApplyDependencyPlan import apply_project_dependency_plan
from liberrpa.ComponentManagement.Application.Project._RepairComponents import repair_project_components
from liberrpa.ComponentManagement.Domain.Dependency._Plan import parse_project_dependency_operation

from pathlib import Path


def handle_request(requestInfo: str) -> DictProtocolResponse:
    try:
        dictRequest = parse_protocol_request(requestInfo)

        match dictRequest["operation"]:
            case "publishComponent":
                return build_publish_response(publish_component(dictRequest["projectPath"]))

            case "importComponentWheels":
                importResult = import_component_wheels([
                    Path(strWheelPath) for strWheelPath in dictRequest["wheelPaths"]
                ])
                return build_component_wheels_imported_response(importResult)

            case "rebuildRepositoryIndex":
                return build_repository_index_rebuilt_response(rebuild_repository_index())

            case "getComponentRepositoryCatalog":
                pathRepository, dictRepositoryIndex, listWarning = load_repository_catalog_snapshot()
                return build_repository_catalog_response(
                    repositoryPath=pathRepository,
                    repositoryIndexDict=dictRepositoryIndex,
                    warningList=listWarning,
                )

            case "getProjectDependencyState":
                stateObj, listWarning = get_current_project_dependency_state(dictRequest["projectPath"])
                return build_project_dependency_state_response(stateObj, listWarning)

            case "buildProjectDependencyPlan":
                operationObj = parse_project_dependency_operation(dictRequest["dependencyOperation"])
                planObj, listWarning = build_current_project_dependency_plan(
                    dictRequest["projectPath"],
                    operationObj,
                )
                return build_project_dependency_plan_response(planObj, listWarning)

            case "applyProjectDependencyPlan":
                operationObj = parse_project_dependency_operation(dictRequest["dependencyOperation"])
                applyResult = apply_project_dependency_plan(
                    Path(dictRequest["projectPath"]),
                    operationObj,
                    dictRequest["confirmedPlanSha256"],
                )
                return build_project_dependency_plan_applied_response(applyResult)

            case "repairProjectComponents":
                repairResult = repair_project_components(Path(dictRequest["projectPath"]))
                return build_project_components_repaired_response(repairResult)

    except ComponentManagementError as e:
        return build_error_response(e)
