# FileName: _Manifest.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

# Handle component.json in a Component Project or Component Wheel.

from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import read_json
from liberrpa.ComponentManagement.Utils._Version import normalize_specifier, normalize_version
from liberrpa.ComponentManagement.Utils._Validation import add_issue, get_package_name_error
from liberrpa.ComponentManagement.Utils._TypedValue import ComponentManifest

from pathlib import Path


import uuid


_SET_COMPONENT_MANIFEST_KEYS = {
    "schemaVersion",
    "id",
    "packageName",
    "displayName",
    "version",
    "description",
    "requiresLiberrpa",
    "componentDependencies",
}


def _normalize_uuid(value: str, field: str, issueList: list[dict[str, object]]) -> str | None:
    try:
        uuidObj = uuid.UUID(value)
    except ValueError:
        add_issue(issueList, field, "Value must be a valid UUID.")
        return None

    if uuidObj.version != 4 or uuidObj.variant != uuid.RFC_4122:
        add_issue(issueList, field, "Value must be a UUID v4.")
        return None

    return str(uuidObj)


def _validate_string_field(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
    *,
    allowEmpty: bool,
) -> str | None:
    if not isinstance(value, str):
        add_issue(issueList, field, "Value must be a string.")
        return None

    if not allowEmpty and value == "":
        add_issue(issueList, field, "Value cannot be empty.")
        return None

    return value


def parse_component_manifest(
    value: object,
    *,
    sourceName: str = "component.json",
) -> ComponentManifest:
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
    setKeys = set(value)

    if setKeys != _SET_COMPONENT_MANIFEST_KEYS:
        listMissingKey = sorted(_SET_COMPONENT_MANIFEST_KEYS - setKeys)
        listUnknownKey = sorted(setKeys - _SET_COMPONENT_MANIFEST_KEYS)

        if listMissingKey:
            add_issue(listIssue, sourceName, f"Missing fields: {listMissingKey}.")

        if listUnknownKey:
            add_issue(listIssue, sourceName, f"Unknown fields: {listUnknownKey}.")

    schemaVersionValue = value.get("schemaVersion")
    if type(schemaVersionValue) is not int or schemaVersionValue != 1:
        add_issue(listIssue, "schemaVersion", "Only schemaVersion 1 is supported.")

    strId = _validate_string_field(
        value.get("id"),
        "id",
        listIssue,
        allowEmpty=False,
    )
    strPackageName = _validate_string_field(
        value.get("packageName"),
        "packageName",
        listIssue,
        allowEmpty=False,
    )
    strDisplayName = _validate_string_field(
        value.get("displayName"),
        "displayName",
        listIssue,
        allowEmpty=False,
    )
    strVersion = _validate_string_field(
        value.get("version"),
        "version",
        listIssue,
        allowEmpty=False,
    )
    strDescription = _validate_string_field(
        value.get("description"),
        "description",
        listIssue,
        allowEmpty=True,
    )
    strRequiresLiberrpa = _validate_string_field(
        value.get("requiresLiberrpa"),
        "requiresLiberrpa",
        listIssue,
        allowEmpty=False,
    )

    strNormalizedId: str | None = None
    if strId is not None:
        if strId != strId.strip():
            add_issue(listIssue, "id", "Value cannot start or end with whitespace.")
        else:
            strNormalizedId = _normalize_uuid(strId, "id", listIssue)

    if strPackageName is not None:
        strPackageNameError = get_package_name_error(strPackageName)
        if strPackageNameError is not None:
            add_issue(listIssue, "packageName", strPackageNameError)

    if strDisplayName is not None:
        if strDisplayName != strDisplayName.strip():
            add_issue(listIssue, "displayName", "Value cannot start or end with whitespace.")
        if "\r" in strDisplayName or "\n" in strDisplayName:
            add_issue(listIssue, "displayName", "Value must be a single line.")

    strNormalizedVersion: str | None = None
    if strVersion is not None:
        if strVersion != strVersion.strip():
            add_issue(listIssue, "version", "Value cannot start or end with whitespace.")
        else:
            try:
                strNormalizedVersion = normalize_version(strVersion)
            except ValueError as e:
                add_issue(listIssue, "version", str(e))

    strNormalizedRequiresLiberrpa: str | None = None
    if strRequiresLiberrpa is not None:
        if strRequiresLiberrpa != strRequiresLiberrpa.strip():
            add_issue(listIssue, "requiresLiberrpa", "Value cannot start or end with whitespace.")
        else:
            try:
                strNormalizedRequiresLiberrpa = normalize_specifier(strRequiresLiberrpa)
            except ValueError as e:
                add_issue(listIssue, "requiresLiberrpa", str(e))

    dependenciesValue = value.get("componentDependencies")
    dictNormalizedDependency: dict[str, str] = {}

    if not isinstance(dependenciesValue, dict):
        add_issue(
            listIssue,
            "componentDependencies",
            "Value must be an object containing Component ID and version range pairs.",
        )
    else:
        setNormalizedDependencyId: set[str] = set()

        for strDependencyId, dependencySpecifierValue in dependenciesValue.items():
            strField = f"componentDependencies.{strDependencyId}"

            if not isinstance(strDependencyId, str):
                add_issue(listIssue, "componentDependencies", "Every Component ID must be a string.")
                continue

            strNormalizedDependencyId = _normalize_uuid(strDependencyId, strField, listIssue)
            if strNormalizedDependencyId is None:
                # The ID has something wrong and an issue has been added.
                continue

            if strNormalizedDependencyId in setNormalizedDependencyId:
                add_issue(listIssue, strField, "The same Component ID is declared more than once.")
                continue

            setNormalizedDependencyId.add(strNormalizedDependencyId)

            if not isinstance(dependencySpecifierValue, str):
                add_issue(listIssue, strField, "Version range must be a string.")
                continue

            if dependencySpecifierValue != dependencySpecifierValue.strip():
                add_issue(listIssue, strField, "Version range cannot start or end with whitespace.")
                continue

            try:
                strNormalizedSpecifier = normalize_specifier(dependencySpecifierValue)
            except ValueError as e:
                add_issue(listIssue, strField, str(e))
                continue

            dictNormalizedDependency[strNormalizedDependencyId] = strNormalizedSpecifier

    if strNormalizedId is not None and strNormalizedId in dictNormalizedDependency:
        add_issue(listIssue, "componentDependencies", "A Component cannot depend on itself.")

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

    return ComponentManifest(
        schemaVersion=1,
        id=strNormalizedId,
        packageName=strPackageName,
        displayName=strDisplayName,
        version=strNormalizedVersion,
        description=strDescription,
        requiresLiberrpa=strNormalizedRequiresLiberrpa,
        componentDependencies=dict(sorted(dictNormalizedDependency.items())),
    )


def read_component_manifest(manifestPath: Path) -> ComponentManifest:
    if not manifestPath.is_file():
        raise ComponentManagementError(
            code="component_manifest_missing",
            message=f"Component Project manifest was not found: {manifestPath}",
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
