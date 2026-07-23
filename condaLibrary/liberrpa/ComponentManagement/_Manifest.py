# FileName: _Manifest.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement._Exception import ComponentManagementError
from liberrpa.ComponentManagement._File import read_json
from liberrpa.ComponentManagement._Version import normalize_specifier, normalize_version

from dataclasses import dataclass
from pathlib import Path
import keyword
import re
import sys
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

_REGEX_COMPONENT_PACKAGE_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")

_SET_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

_SET_PYTHON_STDLIB_MODULE_NAMES = {name.casefold() for name in sys.stdlib_module_names}

_SET_LIBERRPA_THIRD_PARTY_MODULE_NAMES = {
    name.casefold()
    for name in {
        "psutil",
        "PIL",
        "win32clipboard",
        "win32cred",
        "win32gui",
        "win32con",
        "win32com",
        "win32api",
        "pythoncom",
        "pyperclip",
        "pathvalidate",
        "sqlalchemy",
        "pandas",
        "xlwings",
        "pyzipper",
        "pypdf",
        "fitz",
        "ftputil",
        "uiautomation",
        "pynput",
        "pyautogui",
        "imapclient",
        "mailparser",
        "yagmail",
        "json5",
        "easyocr",
        "requests",
        "screeninfo",
        "socketio",
        "flask",
        "flask_socketio",
        "keyboard",
        "pyWinhook",
        "pystray",
        "mss",
        "PyQt5",
    }
}


@dataclass(frozen=True)
class ComponentManifest:
    schemaVersion: int
    id: str
    packageName: str
    displayName: str
    version: str
    description: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


def _add_issue(issues: list[dict[str, object]], field: str, message: str) -> None:
    issues.append({"field": field, "message": message})


def _normalize_uuid(value: str, field: str, issues: list[dict[str, object]]) -> str | None:
    try:
        uuidObj = uuid.UUID(value)
    except ValueError:
        _add_issue(issues, field, "Value must be a valid UUID.")
        return None

    if uuidObj.version != 4 or uuidObj.variant != uuid.RFC_4122:
        _add_issue(issues, field, "Value must be a UUID v4.")
        return None

    return str(uuidObj)


def _get_package_name_error(packageName: str) -> str | None:
    if _REGEX_COMPONENT_PACKAGE_NAME.fullmatch(packageName) is None:
        return "Package name must use PascalCase and contain only ASCII letters and digits, for example: ExcelTools."

    # These checks intentionally overlap with the current PascalCase naming rule.
    # Keep them independent so future changes to the naming convention don't accidentally allow a package name that isn't a valid Python identifier or is reserved by Python.
    if not packageName.isidentifier():
        return "Package name must be a valid Python identifier."

    # Keep these names explicit even though keyword.iskeyword() also rejects them in Python 3.13, so this rule remains visible and independently enforced.
    if packageName in {"False", "None", "True"}:
        return f"Package name cannot use the reserved Python name {packageName!r}."

    if keyword.iskeyword(packageName):
        return f"Package name cannot use the Python keyword {packageName!r}."

    strNormalizedName = packageName.casefold()

    if strNormalizedName == "liberrpa":
        return 'Package name "liberrpa" is reserved by LiberRPA.'

    if packageName.upper() in _SET_RESERVED_WINDOWS_NAMES:
        return f"Package name {packageName!r} is reserved by Windows."

    if strNormalizedName in _SET_PYTHON_STDLIB_MODULE_NAMES:
        return f"Package name {packageName!r} conflicts with a Python standard library module."

    if strNormalizedName in _SET_LIBERRPA_THIRD_PARTY_MODULE_NAMES:
        return f"Package name {packageName!r} conflicts with a third-party package used by LiberRPA."

    return None


def _validate_string_field(
    value: object,
    field: str,
    issues: list[dict[str, object]],
    *,
    allowEmpty: bool,
) -> str | None:
    if not isinstance(value, str):
        _add_issue(issues, field, "Value must be a string.")
        return None

    if not allowEmpty and value == "":
        _add_issue(issues, field, "Value cannot be empty.")
        return None

    return value


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

    if not isinstance(value, dict):
        raise ComponentManagementError(
            code="component_manifest_invalid",
            message="Invalid component.json.",
            details={"issues": [{"field": "component.json", "message": "The root value must be an object."}]},
        )

    listIssue: list[dict[str, object]] = []
    setKeys = set(value)

    if setKeys != _SET_COMPONENT_MANIFEST_KEYS:
        listMissingKey = sorted(_SET_COMPONENT_MANIFEST_KEYS - setKeys)
        listUnknownKey = sorted(setKeys - _SET_COMPONENT_MANIFEST_KEYS)

        if listMissingKey:
            _add_issue(listIssue, "component.json", f"Missing fields: {listMissingKey}.")

        if listUnknownKey:
            _add_issue(listIssue, "component.json", f"Unknown fields: {listUnknownKey}.")

    schemaVersionValue = value.get("schemaVersion")
    if type(schemaVersionValue) is not int or schemaVersionValue != 1:
        _add_issue(listIssue, "schemaVersion", "Only schemaVersion 1 is supported.")

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
            _add_issue(listIssue, "id", "Value cannot start or end with whitespace.")
        else:
            strNormalizedId = _normalize_uuid(strId, "id", listIssue)

    if strPackageName is not None:
        strPackageNameError = _get_package_name_error(strPackageName)
        if strPackageNameError is not None:
            _add_issue(listIssue, "packageName", strPackageNameError)

    if strDisplayName is not None:
        if strDisplayName != strDisplayName.strip():
            _add_issue(listIssue, "displayName", "Value cannot start or end with whitespace.")
        if "\r" in strDisplayName or "\n" in strDisplayName:
            _add_issue(listIssue, "displayName", "Value must be a single line.")

    strNormalizedVersion: str | None = None
    if strVersion is not None:
        if strVersion != strVersion.strip():
            _add_issue(listIssue, "version", "Value cannot start or end with whitespace.")
        else:
            try:
                strNormalizedVersion = normalize_version(strVersion)
            except ValueError as e:
                _add_issue(listIssue, "version", str(e))

    strNormalizedRequiresLiberrpa: str | None = None
    if strRequiresLiberrpa is not None:
        if strRequiresLiberrpa != strRequiresLiberrpa.strip():
            _add_issue(listIssue, "requiresLiberrpa", "Value cannot start or end with whitespace.")
        else:
            try:
                strNormalizedRequiresLiberrpa = normalize_specifier(strRequiresLiberrpa)
            except ValueError as e:
                _add_issue(listIssue, "requiresLiberrpa", str(e))

    dependenciesValue = value.get("componentDependencies")
    dictNormalizedDependency: dict[str, str] = {}

    if not isinstance(dependenciesValue, dict):
        _add_issue(
            listIssue,
            "componentDependencies",
            "Value must be an object containing Component ID and version range pairs.",
        )
    else:
        setNormalizedDependencyId: set[str] = set()

        for strDependencyId, dependencySpecifierValue in dependenciesValue.items():
            strField = f"componentDependencies.{strDependencyId}"

            if not isinstance(strDependencyId, str):
                _add_issue(listIssue, "componentDependencies", "Every Component ID must be a string.")
                continue

            strNormalizedDependencyId = _normalize_uuid(strDependencyId, strField, listIssue)
            if strNormalizedDependencyId is None:
                # The ID has something wrong and an issue has been added.
                continue

            if strNormalizedDependencyId in setNormalizedDependencyId:
                _add_issue(listIssue, strField, "The same Component ID is declared more than once.")
                continue

            setNormalizedDependencyId.add(strNormalizedDependencyId)

            if not isinstance(dependencySpecifierValue, str):
                _add_issue(listIssue, strField, "Version range must be a string.")
                continue

            if dependencySpecifierValue != dependencySpecifierValue.strip():
                _add_issue(listIssue, strField, "Version range cannot start or end with whitespace.")
                continue

            try:
                strNormalizedSpecifier = normalize_specifier(dependencySpecifierValue)
            except ValueError as e:
                _add_issue(listIssue, strField, str(e))
                continue

            dictNormalizedDependency[strNormalizedDependencyId] = strNormalizedSpecifier

    if strNormalizedId is not None and strNormalizedId in dictNormalizedDependency:
        _add_issue(listIssue, "componentDependencies", "A Component cannot depend on itself.")

    if listIssue:
        raise ComponentManagementError(
            code="component_manifest_invalid",
            message="Invalid component.json.",
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
