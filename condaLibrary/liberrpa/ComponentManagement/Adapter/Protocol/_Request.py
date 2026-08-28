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
    DictProtocolRequest_ImportComponentWheels,
    DictProtocolRequest_RebuildRepositoryIndex,
    DictProtocolRequest_GetComponentRepositoryCatalog,
    DictProtocolRequest_GetProjectManifestDefaults,
    DictProtocolRequest_GetProjectDependencyState,
    DictProtocolRequest_BuildProjectDependencyPlan,
    DictProtocolRequest_ApplyProjectDependencyPlan,
    DictProtocolRequest_RepairProjectComponents,
    DictProtocolRequest,
)
from liberrpa.ComponentManagement.Domain.Repository._Index import validate_sha256

from typing import NoReturn, cast


_SET_REQUEST_KEYS_PUBLISH_COMPONENT = {
    "schemaVersion",
    "operation",
    "projectPath",
}
_SET_REQUEST_KEYS_IMPORT_COMPONENT_WHEELS = {
    "schemaVersion",
    "operation",
    "wheelFilePaths",
}
_SET_REQUEST_KEYS_REBUILD_REPOSITORY_INDEX = {
    "schemaVersion",
    "operation",
}
_SET_REQUEST_KEYS_GET_COMPONENT_REPOSITORY_CATALOG = {
    "schemaVersion",
    "operation",
}
_SET_REQUEST_KEYS_GET_PROJECT_MANIFEST_DEFAULTS = {
    "schemaVersion",
    "operation",
}
_SET_REQUEST_KEYS_GET_PROJECT_DEPENDENCY_STATE = {
    "schemaVersion",
    "operation",
    "projectPath",
}
_SET_REQUEST_KEYS_BUILD_PROJECT_DEPENDENCY_PLAN = {
    "schemaVersion",
    "operation",
    "projectPath",
    "dependencyOperation",
}
_SET_REQUEST_KEYS_APPLY_PROJECT_DEPENDENCY_PLAN = {
    "schemaVersion",
    "operation",
    "projectPath",
    "dependencyOperation",
    "confirmedPlanSha256",
}
_SET_REQUEST_KEYS_REPAIR_PROJECT_COMPONENTS = {
    "schemaVersion",
    "operation",
    "projectPath",
}


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


def _validate_project_path_value(value: object) -> None:
    if not isinstance(value, str) or value.strip() == "":
        _raise_invalid_request("projectPath must be a non-empty string.")


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
        _raise_invalid_request(
            "Only Component Management protocol schemaVersion 1 is supported."
        )

    operation = value.get("operation")
    match operation:
        case "publishComponent":
            _validate_request_keys(
                value, _SET_REQUEST_KEYS_PUBLISH_COMPONENT, "Publish Component"
            )

            _validate_project_path_value(value.get("projectPath"))

            return cast(DictProtocolRequest_PublishComponent, value)

        case "importComponentWheels":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_IMPORT_COMPONENT_WHEELS,
                "Import Component Wheels",
            )

            wheelFilePaths = value.get("wheelFilePaths")
            if not isinstance(wheelFilePaths, list) or not wheelFilePaths:
                _raise_invalid_request(
                    "wheelFilePaths must be a non-empty array of strings."
                )
            if any(
                not isinstance(wheelFilePath, str) or wheelFilePath.strip() == ""
                for wheelFilePath in wheelFilePaths
            ):
                _raise_invalid_request(
                    "wheelFilePaths must be a non-empty array of strings."
                )

            return cast(DictProtocolRequest_ImportComponentWheels, value)

        case "rebuildRepositoryIndex":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_REBUILD_REPOSITORY_INDEX,
                "Rebuild Repository Index",
            )
            return cast(DictProtocolRequest_RebuildRepositoryIndex, value)

        case "getComponentRepositoryCatalog":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_GET_COMPONENT_REPOSITORY_CATALOG,
                "Get Component Repository Catalog",
            )
            return cast(DictProtocolRequest_GetComponentRepositoryCatalog, value)

        case "getProjectManifestDefaults":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_GET_PROJECT_MANIFEST_DEFAULTS,
                "Get Project Manifest Defaults",
            )

            return cast(DictProtocolRequest_GetProjectManifestDefaults, value)

        case "getProjectDependencyState":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_GET_PROJECT_DEPENDENCY_STATE,
                "Get Project Dependency State",
            )

            _validate_project_path_value(value.get("projectPath"))

            return cast(DictProtocolRequest_GetProjectDependencyState, value)

        case "buildProjectDependencyPlan":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_BUILD_PROJECT_DEPENDENCY_PLAN,
                "Build Project Dependency Plan",
            )

            _validate_project_path_value(value.get("projectPath"))
            if not isinstance(value.get("dependencyOperation"), dict):
                _raise_invalid_request("dependencyOperation must be an object.")

            return cast(DictProtocolRequest_BuildProjectDependencyPlan, value)

        case "applyProjectDependencyPlan":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_APPLY_PROJECT_DEPENDENCY_PLAN,
                "Apply Project Dependency Plan",
            )

            _validate_project_path_value(value.get("projectPath"))
            if not isinstance(value.get("dependencyOperation"), dict):
                _raise_invalid_request("dependencyOperation must be an object.")
            try:
                validate_sha256(value.get("confirmedPlanSha256"), "confirmedPlanSha256")
            except ValueError as e:
                _raise_invalid_request(str(e))

            return cast(DictProtocolRequest_ApplyProjectDependencyPlan, value)

        case "repairProjectComponents":
            _validate_request_keys(
                value,
                _SET_REQUEST_KEYS_REPAIR_PROJECT_COMPONENTS,
                "Repair Project Components",
            )

            _validate_project_path_value(value.get("projectPath"))

            return cast(DictProtocolRequest_RepairProjectComponents, value)

        case _:
            _raise_invalid_request(
                f"Unsupported Component Management operation: {operation!r}.",
            )
