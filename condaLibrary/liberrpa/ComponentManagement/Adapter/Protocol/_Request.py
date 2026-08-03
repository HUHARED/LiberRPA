# FileName: _Request.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import parse_json
from liberrpa.ComponentManagement.Common._Validation import validate_exact_keys
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
)

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


def parse_protocol_request(requestInfo: str) -> DictProtocolRequest:
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
