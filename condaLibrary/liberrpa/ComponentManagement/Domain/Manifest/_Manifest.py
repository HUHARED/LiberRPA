# FileName: _Manifest.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

# Handle flow.json and component.json in a Project or Component Wheel.

from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import read_json
from liberrpa.ComponentManagement.Common._Version import (
    normalize_pep440_version,
    normalize_pep440_specifier,
)
from liberrpa.ComponentManagement.Common._Validation import (
    add_validation_issue,
    get_package_name_error,
    path_exists,
    is_file_invalid,
)
from liberrpa.ComponentManagement.Types._Manifest import (
    Str_ProjectType,
    Info_ProjectManifest_Flow,
    Info_ProjectManifest_Component,
    Info_ProjectManifest,
)


from pathlib import Path


import uuid


_SET_MANIFEST_KEYS_FLOW = {
    "schemaVersion",
    "name",
    "version",
    "description",
    "requiresLiberrpa",
    "componentDependencies",
}

_SET_MANIFEST_KEYS_COMPONENT = {
    "schemaVersion",
    "id",
    "packageName",
    "displayName",
    "version",
    "description",
    "requiresLiberrpa",
    "componentDependencies",
}


def _validate_uuid(
    value: str, field: str, issueList: list[dict[str, object]]
) -> str | None:
    try:
        uuidObj = uuid.UUID(value)
    except ValueError:
        add_validation_issue(issueList, field, "Value must be a valid UUID.")
        return None

    if uuidObj.version != 4 or uuidObj.variant != uuid.RFC_4122:
        add_validation_issue(issueList, field, "Value must be a UUID v4.")
        return None

    if value != str(uuidObj):
        add_validation_issue(
            issueList,
            field,
            "Value must use the canonical lowercase UUID format with hyphens.",
        )
        return None

    return value


def _validate_manifest_keys(
    value: dict[str, object],
    expectedKeySet: set[str],
    sourceName: str,
    issueList: list[dict[str, object]],
) -> None:
    setKey = set(value)
    listMissingKey = sorted(expectedKeySet - setKey)
    listUnknownKey = sorted(setKey - expectedKeySet)

    if listMissingKey:
        add_validation_issue(issueList, sourceName, f"Missing fields: {listMissingKey}.")

    if listUnknownKey:
        add_validation_issue(issueList, sourceName, f"Unknown fields: {listUnknownKey}.")


def _validate_string_field(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
    *,
    allowEmpty: bool,
) -> str | None:
    if not isinstance(value, str):
        add_validation_issue(issueList, field, "Value must be a string.")
        return None

    if not allowEmpty and value == "":
        add_validation_issue(issueList, field, "Value cannot be empty.")
        return None

    return value


def _validate_trimmed_single_line_field(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    strValue = _validate_string_field(value, field, issueList, allowEmpty=False)
    if strValue is None:
        return None

    boolValid = True
    if strValue != strValue.strip():
        add_validation_issue(issueList, field, "Value cannot start or end with whitespace.")
        boolValid = False

    if "\r" in strValue or "\n" in strValue:
        add_validation_issue(issueList, field, "Value must be a single line.")
        boolValid = False

    return strValue if boolValid else None


def _validate_uuid_field(
    value: object, field: str, issueList: list[dict[str, object]]
) -> str | None:
    strValue = _validate_string_field(
        value,
        field,
        issueList,
        allowEmpty=False,
    )
    if strValue is None:
        return None

    if strValue != strValue.strip():
        add_validation_issue(issueList, field, "Value cannot start or end with whitespace.")
        return None

    return _validate_uuid(strValue, field, issueList)


def _validate_package_name_field(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    strValue = _validate_string_field(value, field, issueList, allowEmpty=False)
    if strValue is None:
        return None

    strPackageNameError = get_package_name_error(strValue)
    if strPackageNameError is not None:
        add_validation_issue(issueList, field, strPackageNameError)
        return None

    return strValue


def _parse_version_field(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    strValue = _validate_string_field(value, field, issueList, allowEmpty=False)
    if strValue is None:
        return None

    if strValue != strValue.strip():
        add_validation_issue(issueList, field, "Value cannot start or end with whitespace.")
        return None

    try:
        return normalize_pep440_version(strValue)
    except ValueError as e:
        add_validation_issue(issueList, field, str(e))
        return None


def _parse_version_specifier_field(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    strValue = _validate_string_field(value, field, issueList, allowEmpty=False)
    if strValue is None:
        return None

    if strValue != strValue.strip():
        add_validation_issue(issueList, field, "Value cannot start or end with whitespace.")
        return None

    try:
        return normalize_pep440_specifier(strValue)
    except ValueError as e:
        add_validation_issue(issueList, field, str(e))
        return None


def _parse_component_dependencies(
    value: object,
    issueList: list[dict[str, object]],
    *,
    rootComponentId: str | None = None,
) -> dict[str, str]:
    dictNormalizedDependency: dict[str, str] = {}

    if not isinstance(value, dict):
        add_validation_issue(
            issueList,
            "componentDependencies",
            "Value must be an object containing Component ID and version range pairs.",
        )
        return dictNormalizedDependency

    setNormalizedDependencyId: set[str] = set()

    for dependencyId, dependencySpecifierValue in value.items():
        if not isinstance(dependencyId, str):
            add_validation_issue(
                issueList, "componentDependencies", "Every Component ID must be a string."
            )
            continue

        strField = f"componentDependencies.{dependencyId}"
        strNormalizedDependencyId = _validate_uuid(dependencyId, strField, issueList)
        if strNormalizedDependencyId is None:
            continue

        if strNormalizedDependencyId in setNormalizedDependencyId:
            add_validation_issue(
                issueList, strField, "The same Component ID is declared more than once."
            )
            continue

        setNormalizedDependencyId.add(strNormalizedDependencyId)

        if not isinstance(dependencySpecifierValue, str):
            add_validation_issue(issueList, strField, "Version range must be a string.")
            continue

        if dependencySpecifierValue != dependencySpecifierValue.strip():
            add_validation_issue(
                issueList, strField, "Version range cannot start or end with whitespace."
            )
            continue

        try:
            strNormalizedSpecifier = normalize_pep440_specifier(dependencySpecifierValue)
        except ValueError as e:
            add_validation_issue(issueList, strField, str(e))
            continue

        dictNormalizedDependency[strNormalizedDependencyId] = strNormalizedSpecifier

    if rootComponentId is not None and rootComponentId in dictNormalizedDependency:
        add_validation_issue(
            issueList, "componentDependencies", "A Component cannot depend on itself."
        )

    return dict(sorted(dictNormalizedDependency.items()))


def parse_flow_manifest(
    value: object,
    *,
    sourceName: str = "flow.json",
) -> Info_ProjectManifest_Flow:
    if not isinstance(value, dict):
        raise ComponentManagementError(
            code="flow_manifest_invalid",
            message=f"Invalid {sourceName}.",
            details={
                "issues": [
                    {
                        "field": sourceName,
                        "message": "The root value must be an object.",
                    },
                ]
            },
        )

    listIssue: list[dict[str, object]] = []
    _validate_manifest_keys(value, _SET_MANIFEST_KEYS_FLOW, sourceName, listIssue)

    schemaVersionValue = value.get("schemaVersion")
    if type(schemaVersionValue) is not int or schemaVersionValue != 1:
        add_validation_issue(listIssue, "schemaVersion", "Only schemaVersion 1 is supported.")

    strName = _validate_trimmed_single_line_field(value.get("name"), "name", listIssue)
    strNormalizedVersion = _parse_version_field(
        value.get("version"), "version", listIssue
    )
    strDescription = _validate_string_field(
        value.get("description"),
        "description",
        listIssue,
        allowEmpty=True,
    )
    strNormalizedRequiresLiberrpa = _parse_version_specifier_field(
        value.get("requiresLiberrpa"),
        "requiresLiberrpa",
        listIssue,
    )

    dictNormalizedDependency = _parse_component_dependencies(
        value.get("componentDependencies"),
        listIssue,
    )

    if listIssue:
        raise ComponentManagementError(
            code="flow_manifest_invalid",
            message=f"Invalid {sourceName}.",
            details={"issues": listIssue},
        )

    assert strName is not None
    assert strNormalizedVersion is not None
    assert strDescription is not None
    assert strNormalizedRequiresLiberrpa is not None

    return Info_ProjectManifest_Flow(
        name=strName,
        version=strNormalizedVersion,
        description=strDescription,
        requiresLiberrpa=strNormalizedRequiresLiberrpa,
        componentDependencies=dictNormalizedDependency,
    )


def parse_component_manifest(
    value: object,
    *,
    sourceName: str = "component.json",
) -> Info_ProjectManifest_Component:
    if not isinstance(value, dict):
        raise ComponentManagementError(
            code="component_manifest_invalid",
            message=f"Invalid {sourceName}.",
            details={
                "issues": [
                    {
                        "field": sourceName,
                        "message": "The root value must be an object.",
                    },
                ]
            },
        )

    listIssue: list[dict[str, object]] = []
    _validate_manifest_keys(value, _SET_MANIFEST_KEYS_COMPONENT, sourceName, listIssue)

    schemaVersionValue = value.get("schemaVersion")
    if type(schemaVersionValue) is not int or schemaVersionValue != 1:
        add_validation_issue(listIssue, "schemaVersion", "Only schemaVersion 1 is supported.")

    strNormalizedId = _validate_uuid_field(value.get("id"), "id", listIssue)
    strPackageName = _validate_package_name_field(
        value.get("packageName"), "packageName", listIssue
    )
    strDisplayName = _validate_trimmed_single_line_field(
        value.get("displayName"), "displayName", listIssue
    )
    strNormalizedVersion = _parse_version_field(
        value.get("version"), "version", listIssue
    )
    strDescription = _validate_string_field(
        value.get("description"),
        "description",
        listIssue,
        allowEmpty=True,
    )
    strNormalizedRequiresLiberrpa = _parse_version_specifier_field(
        value.get("requiresLiberrpa"),
        "requiresLiberrpa",
        listIssue,
    )

    dictNormalizedDependency = _parse_component_dependencies(
        value.get("componentDependencies"),
        listIssue,
        rootComponentId=strNormalizedId,
    )

    if listIssue:
        raise ComponentManagementError(
            code="component_manifest_invalid",
            message=f"Invalid {sourceName}.",
            details={"issues": listIssue},
        )

    assert strNormalizedId is not None
    assert strPackageName is not None
    assert strDisplayName is not None
    assert strNormalizedVersion is not None
    assert strDescription is not None
    assert strNormalizedRequiresLiberrpa is not None

    return Info_ProjectManifest_Component(
        id=strNormalizedId,
        packageName=strPackageName,
        displayName=strDisplayName,
        version=strNormalizedVersion,
        description=strDescription,
        requiresLiberrpa=strNormalizedRequiresLiberrpa,
        componentDependencies=dictNormalizedDependency,
    )


def build_project_manifest_dict(manifestObj: Info_ProjectManifest) -> dict[str, object]:
    dictDependency = dict(sorted(manifestObj.componentDependencies.items()))

    if isinstance(manifestObj, Info_ProjectManifest_Flow):
        return {
            "schemaVersion": 1,
            "name": manifestObj.name,
            "version": manifestObj.version,
            "description": manifestObj.description,
            "requiresLiberrpa": manifestObj.requiresLiberrpa,
            "componentDependencies": dictDependency,
        }

    return {
        "schemaVersion": 1,
        "id": manifestObj.id,
        "packageName": manifestObj.packageName,
        "displayName": manifestObj.displayName,
        "version": manifestObj.version,
        "description": manifestObj.description,
        "requiresLiberrpa": manifestObj.requiresLiberrpa,
        "componentDependencies": dictDependency,
    }


def read_flow_manifest(manifestPath: Path) -> Info_ProjectManifest_Flow:
    if not path_exists(manifestPath):
        raise ComponentManagementError(
            code="flow_manifest_missing",
            message=f"Flow Project manifest was not found: {manifestPath}",
        )

    if is_file_invalid(manifestPath):
        raise ComponentManagementError(
            code="flow_manifest_invalid",
            message=f"Flow Project manifest path is invalid: {manifestPath}",
        )

    try:
        value = read_json(manifestPath)
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="flow_manifest_invalid",
            message="Failed to read flow.json.",
            details={"issues": [{"field": "flow.json", "message": str(e)}]},
        ) from e

    return parse_flow_manifest(value)


def read_component_manifest(manifestPath: Path) -> Info_ProjectManifest_Component:
    if not path_exists(manifestPath):
        raise ComponentManagementError(
            code="component_manifest_missing",
            message=f"Component Project manifest was not found: {manifestPath}",
        )

    if is_file_invalid(manifestPath):
        raise ComponentManagementError(
            code="component_manifest_invalid",
            message=f"Component Project manifest path is invalid: {manifestPath}",
        )

    try:
        value = read_json(manifestPath)
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="component_manifest_invalid",
            message="Failed to read component.json.",
            details={"issues": [{"field": "component.json", "message": str(e)}]},
        ) from e

    return parse_component_manifest(value)


def read_project_manifest(
    projectPath: Path,
) -> tuple[Str_ProjectType, Info_ProjectManifest]:
    pathFlowManifest = projectPath / "flow.json"
    pathComponentManifest = projectPath / "component.json"

    boolHasFlowManifest = path_exists(pathFlowManifest)
    boolHasComponentManifest = path_exists(pathComponentManifest)

    if boolHasFlowManifest and boolHasComponentManifest:
        raise ComponentManagementError(
            code="project_manifest_conflict",
            message="A Project cannot contain both flow.json and component.json.",
            details={
                "flowManifest": str(pathFlowManifest),
                "componentManifest": str(pathComponentManifest),
            },
        )

    if boolHasFlowManifest:
        return "flow", read_flow_manifest(pathFlowManifest)

    if boolHasComponentManifest:
        return "component", read_component_manifest(pathComponentManifest)

    raise ComponentManagementError(
        code="project_manifest_missing",
        message="The Project does not contain flow.json or component.json.",
        details={"projectPath": str(projectPath)},
    )
