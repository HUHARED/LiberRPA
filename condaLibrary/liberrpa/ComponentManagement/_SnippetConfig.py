# FileName: _SnippetConfig.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import read_jsonc, write_text_atomic
from liberrpa.ComponentManagement.Utils._TypedValue import (
    ComponentManifest,
    SnippetInsertionMode,
    DictSnippetImports,
    DictNormalizedSnippet,
    DictAstSnippetsFile,
    DictImportSourceConfig,
    DictSnippetCatalogFile,
    DictAstSnippetOverride,
    DictSnippetConfigWarning,
)
from liberrpa.ComponentManagement.Utils._Validation import add_issue, validate_json_object_fields

from pathlib import Path
from copy import deepcopy
import keyword
from dataclasses import dataclass


_PATH_TEMPLATE = Path(__file__).resolve().parent / "Templates/snippets.jsonc.template"


_SET_SNIPPET_CONFIG_KEYS = {
    # snippets.jsonc.template has the four keys only.
    "schemaVersion",
    "excludedAstSnippets",
    "astSnippetOverrides",
    "snippets",
}

_SET_AST_SNIPPET_OVERRIDE_ALLOWED_KEYS = {
    "label",
    "body",
    "description",
    "insertionMode",
    "imports",
}

_SET_HAND_WRITTEN_SNIPPET_ALLOWED_KEYS = {
    "prefix",
    "label",
    "body",
    "description",
    "insertionMode",
    "imports",
}

# Keep this order synchronized with MANAGED_IMPORT_ORDER in snippets/ApiConfig.py.
# The Snippet generation scripts are not imported by the runtime liberrpa package.
_TUPLE_LIBERRPA_IMPORT_ORDER = (
    "Log",
    "delay",
    "get_component_resource_path",
    #
    "Mouse",
    "Keyboard",
    "Window",
    "UiInterface",
    #
    "Browser",
    "Excel",
    "Outlook",
    "Application",
    "Database",
    #
    "Data",
    "Str",
    "List",
    "Dict",
    "Regex",
    "Math",
    "Time",
    "File",
    "OCR",
    #
    "Web",
    "Mail",
    "FTP",
    #
    "Clipboard",
    "System",
    "Credential",
    #
    "ScreenPrint",
    "Dialog",
    "Trigger",
    #
    "DatabaseConnection",
    "PrjArgs",
    "CustomArgs",
)


@dataclass(frozen=True)
class _SnippetCatalogBuildResult:
    catalog: DictSnippetCatalogFile
    warnings: list[DictSnippetConfigWarning]
    excludedCount: int
    handWrittenCount: int


def _normalize_single_line_string(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    """Validate a non-empty single-line Snippet label or prefix."""
    if not isinstance(value, str) or value == "":
        add_issue(issueList, field, "Value must be a non-empty string.")
        return None

    if "\r" in value or "\n" in value:
        add_issue(issueList, field, "Value must be a single line.")
        return None

    return value


def _normalize_description(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    if not isinstance(value, str) or value == "":
        add_issue(issueList, field, "Value must be a non-empty string.")
        return None

    return value


def _normalize_insertion_mode(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> SnippetInsertionMode | None:
    if value == "line":
        return "line"

    if value == "cursor":
        return "cursor"

    add_issue(
        issueList,
        field,
        'Value must be either "line" or "cursor".',
    )
    return None


def _normalize_snippet_body(
    value: object,
    insertionMode: SnippetInsertionMode,
    field: str,
    issueList: list[dict[str, object]],
) -> list[str] | None:
    if isinstance(value, str):
        listBodyLine = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        listBodyLine = list(value)
    else:
        add_issue(issueList, field, "Value must be a string or a list of strings.")
        return None

    if not listBodyLine or all(line == "" for line in listBodyLine):
        add_issue(issueList, field, "Snippet body cannot be empty.")
        return None

    if insertionMode == "line":
        if listBodyLine[-1] == "":
            listBodyLine[-1] = "$0"
        elif listBodyLine[-1] != "$0":
            listBodyLine.append("$0")
        else:
            pass

    return listBodyLine


def _normalize_imports(
    value: object,
    field: str,
    availableImportOrder: dict[str, tuple[str, ...]],
    issueList: list[dict[str, object]],
) -> DictSnippetImports | None:
    if not isinstance(value, dict):
        add_issue(issueList, field, "Value must be an object containing import source and name-list pairs.")
        return None

    dictResult: DictSnippetImports = {}

    for importSource, importNameValue in value.items():
        strImportField = f"{field}.{importSource}"

        if not isinstance(importSource, str) or importSource == "":
            add_issue(issueList, field, "Every import source must be a non-empty string.")
            continue

        if importSource not in availableImportOrder:
            add_issue(
                issueList,
                strImportField,
                f"Import source is not available to this Component Snippet: {importSource!r}.",
            )
            continue

        if not isinstance(importNameValue, list) or not importNameValue:
            add_issue(issueList, strImportField, "Import names must be a non-empty list.")
            continue

        listImportName: list[str] = []
        setImportName: set[str] = set()

        for importName in importNameValue:
            if not isinstance(importName, str) or not importName.isidentifier() or keyword.iskeyword(importName):
                add_issue(
                    issueList,
                    strImportField,
                    f"Import name must be a valid non-keyword Python identifier: {importName!r}.",
                )
                continue

            if importName in setImportName:
                add_issue(issueList, strImportField, f"Duplicate import name: {importName!r}.")
                continue

            setImportName.add(importName)
            listImportName.append(importName)

        tupleImportOrder = availableImportOrder[importSource]
        dictImportIndex = {name: index for index, name in enumerate(tupleImportOrder)}
        listUnknownImportName = sorted(name for name in listImportName if name not in dictImportIndex)

        if listUnknownImportName:
            add_issue(
                issueList,
                strImportField,
                f"Import names are not available from {importSource!r}: {listUnknownImportName}.",
            )
            continue

        dictResult[importSource] = sorted(listImportName, key=dictImportIndex.__getitem__)

    return dict(sorted(dictResult.items()))


def _normalize_override(
    value: object,
    field: str,
    availableImportOrder: dict[str, tuple[str, ...]],
    issueList: list[dict[str, object]],
) -> DictAstSnippetOverride | None:
    if not isinstance(value, dict):
        add_issue(issueList, field, "Value must be an object.")
        return None

    validate_json_object_fields(
        value,
        _SET_AST_SNIPPET_OVERRIDE_ALLOWED_KEYS,
        field,
        issueList,
    )
    dictResult: DictAstSnippetOverride = {}

    if "label" in value:
        strLabel = _normalize_single_line_string(value["label"], f"{field}.label", issueList)
        if strLabel is not None:
            dictResult["label"] = strLabel

    if "description" in value:
        strDescription = _normalize_description(value["description"], f"{field}.description", issueList)
        if strDescription is not None:
            dictResult["description"] = strDescription

    insertionMode: SnippetInsertionMode | None = None
    if "insertionMode" in value:
        insertionMode = _normalize_insertion_mode(value["insertionMode"], f"{field}.insertionMode", issueList)
        if insertionMode is not None:
            dictResult["insertionMode"] = insertionMode

    if "body" in value:
        bodyInsertionMode: SnippetInsertionMode = insertionMode or "line"
        listBody = _normalize_snippet_body(value["body"], bodyInsertionMode, f"{field}.body", issueList)
        if listBody is not None:
            dictResult["body"] = listBody

    if "imports" in value:
        dictImports = _normalize_imports(value["imports"], f"{field}.imports", availableImportOrder, issueList)
        if dictImports is not None:
            dictResult["imports"] = dictImports

    return dictResult


def _parse_component_snippet_key(
    snippetKey: str,
    packageName: str,
    publicModuleNameSet: set[str],
    field: str,
    issueList: list[dict[str, object]],
    *,
    requireExistingModule: bool,
) -> tuple[str, str, str] | None:
    """Validate a Component Snippet key and append any validation issues."""
    strCategory, strSeparator, strSnippetName = snippetKey.partition(".")
    strCategoryPrefix = f"{packageName}_"

    if strSeparator == "" or "." in strSnippetName or not strCategory.startswith(strCategoryPrefix):
        add_issue(
            issueList,
            field,
            f"Snippet key must use {packageName}_ModuleName.snippet_name.",
        )
        return None

    strModuleName = strCategory[len(strCategoryPrefix) :]
    if strModuleName == "":
        add_issue(issueList, field, "Snippet key must contain a public Component Module name.")
        return None

    if requireExistingModule and strModuleName not in publicModuleNameSet:
        add_issue(
            issueList,
            field,
            f"Public Component Module was not found: {strModuleName!r}.",
        )
        return None

    if not strSnippetName.isidentifier() or keyword.iskeyword(strSnippetName):
        add_issue(
            issueList,
            field,
            f"Snippet name must be a valid non-keyword Python identifier: {strSnippetName!r}.",
        )
        return None

    return strCategory, strModuleName, strSnippetName


def _merge_imports(
    mandatoryImports: DictSnippetImports,
    additionalImports: DictSnippetImports,
    availableImportOrder: dict[str, tuple[str, ...]],
) -> DictSnippetImports:
    dictMergedImport: dict[str, set[str]] = {}

    for imports in (mandatoryImports, additionalImports):
        for importSource, listImportName in imports.items():
            dictMergedImport.setdefault(importSource, set()).update(listImportName)

    dictResult: DictSnippetImports = {}

    for importSource in sorted(dictMergedImport):
        dictImportIndex = {name: index for index, name in enumerate(availableImportOrder[importSource])}
        dictResult[importSource] = sorted(
            dictMergedImport[importSource],
            key=dictImportIndex.__getitem__,
        )

    return dictResult


def _normalize_hand_written_snippet(
    snippetKey: str,
    value: object,
    packageName: str,
    publicModuleNameSet: set[str],
    availableImportOrder: dict[str, tuple[str, ...]],
    issueList: list[dict[str, object]],
) -> DictNormalizedSnippet | None:
    strField = f"snippets.{snippetKey}"
    tupleKeyPart = _parse_component_snippet_key(
        snippetKey=snippetKey,
        packageName=packageName,
        publicModuleNameSet=publicModuleNameSet,
        field=strField,
        issueList=issueList,
        requireExistingModule=True,
    )

    if not isinstance(value, dict):
        add_issue(issueList, strField, "Value must be an object.")
        return None

    validate_json_object_fields(
        value,
        _SET_HAND_WRITTEN_SNIPPET_ALLOWED_KEYS,
        strField,
        issueList,
    )

    if tupleKeyPart is None:
        return None

    strCategory, strModuleName, strSnippetName = tupleKeyPart

    strPrefix = snippetKey
    if "prefix" in value:
        normalizedPrefix = _normalize_single_line_string(value["prefix"], f"{strField}.prefix", issueList)
        if normalizedPrefix is not None:
            strPrefix = normalizedPrefix

    strLabel = strSnippetName
    if "label" in value:
        normalizedLabel = _normalize_single_line_string(value["label"], f"{strField}.label", issueList)
        if normalizedLabel is not None:
            strLabel = normalizedLabel

    insertionMode: SnippetInsertionMode = "line"
    if "insertionMode" in value:
        normalizedInsertionMode = _normalize_insertion_mode(
            value["insertionMode"],
            f"{strField}.insertionMode",
            issueList,
        )
        if normalizedInsertionMode is not None:
            insertionMode = normalizedInsertionMode

    if "body" not in value:
        add_issue(issueList, strField, "Missing required field: body.")
        listBody = None
    else:
        listBody = _normalize_snippet_body(value["body"], insertionMode, f"{strField}.body", issueList)

    if "description" not in value:
        add_issue(issueList, strField, "Missing required field: description.")
        strDescription = None
    else:
        strDescription = _normalize_description(value["description"], f"{strField}.description", issueList)

    dictAdditionalImport: DictSnippetImports = {}
    if "imports" in value:
        normalizedImports = _normalize_imports(
            value["imports"],
            f"{strField}.imports",
            availableImportOrder,
            issueList,
        )
        if normalizedImports is not None:
            dictAdditionalImport = normalizedImports

    if listBody is None or strDescription is None:
        return None

    dictMandatoryImport: DictSnippetImports = {packageName: [strModuleName]}

    return {
        "category": strCategory,
        "label": strLabel,
        "prefix": strPrefix,
        "body": listBody,
        "description": strDescription,
        "insertionMode": insertionMode,
        "imports": _merge_imports(
            mandatoryImports=dictMandatoryImport,
            additionalImports=dictAdditionalImport,
            availableImportOrder=availableImportOrder,
        ),
    }


def _stabilize_snippet(snippet: DictNormalizedSnippet) -> DictNormalizedSnippet:
    return {
        "category": snippet["category"],
        "label": snippet["label"],
        "prefix": snippet["prefix"],
        "body": list(snippet["body"]),
        "description": snippet["description"],
        "insertionMode": snippet["insertionMode"],
        "imports": {importSource: list(importName) for importSource, importName in snippet["imports"].items()},
    }


def create_snippet_config(configPath: Path) -> bool:
    if configPath.exists():
        if not configPath.is_file():
            raise ComponentManagementError(
                code="snippet_config_invalid",
                message=f"Snippet configuration path is not a file: {configPath}",
            )
        return False

    try:
        strTemplate = _PATH_TEMPLATE.read_text(encoding="utf-8", errors="strict")
    except OSError as e:
        raise ComponentManagementError(
            code="snippet_template_missing",
            message=f"Failed to read the Component Snippet template: {_PATH_TEMPLATE}",
        ) from e

    if strTemplate.strip() == "":
        raise ComponentManagementError(
            code="snippet_template_invalid",
            message=f"The Component Snippet template is empty: {_PATH_TEMPLATE}",
        )

    try:
        write_text_atomic(path=configPath, text=strTemplate.rstrip("\r\n") + "\n")
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to create Component Snippet configuration: {configPath}",
        ) from e

    return True


def raise_config_issues(issueList: list[dict[str, object]]) -> None:
    if not issueList:
        return

    raise ComponentManagementError(
        code="snippet_config_invalid",
        message="Invalid Component Snippet configuration.",
        details={"issues": issueList},
    )


def build_snippet_catalog(
    configPath: Path,
    astSnippets: DictAstSnippetsFile,
    packagePath: Path,
    manifestObj: ComponentManifest,
) -> _SnippetCatalogBuildResult:
    try:
        value = read_jsonc(configPath)
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="snippet_config_invalid",
            message="Failed to read snippets.jsonc.",
            details={"issues": [{"field": "snippets.jsonc", "message": str(e)}]},
        ) from e

    if not isinstance(value, dict):
        raise ComponentManagementError(
            code="snippet_config_invalid",
            message="Invalid Component Snippet configuration.",
            details={"issues": [{"field": "snippets.jsonc", "message": "The root value must be an object."}]},
        )

    listIssue: list[dict[str, object]] = []
    validate_json_object_fields(
        value,
        _SET_SNIPPET_CONFIG_KEYS,
        "snippets.jsonc",
        listIssue,
    )

    schemaVersionValue = value.get("schemaVersion")
    if type(schemaVersionValue) is not int or schemaVersionValue != 1:
        add_issue(listIssue, "schemaVersion", "Only schemaVersion 1 is supported.")

    listPublicModuleName = sorted(
        modulePath.stem
        for modulePath in packagePath.iterdir()
        if modulePath.is_file()
        and modulePath.suffix.casefold() == ".py"
        and modulePath.name != "__init__.py"
        and not modulePath.name.startswith("_")
    )
    setPublicModuleName = set(listPublicModuleName)
    dictAvailableImportOrder: dict[str, tuple[str, ...]] = {
        "liberrpa.Modules": _TUPLE_LIBERRPA_IMPORT_ORDER,
        manifestObj.packageName: tuple(listPublicModuleName),
    }

    listExcludedValue = value.get("excludedAstSnippets")
    setExcludedSnippet: set[str] = set()

    if not isinstance(listExcludedValue, list):
        add_issue(listIssue, "excludedAstSnippets", "Value must be a list of Snippet keys.")
    else:
        for intIndex, strSnippetKey in enumerate(listExcludedValue):
            strField = f"excludedAstSnippets[{intIndex}]"

            if not isinstance(strSnippetKey, str):
                add_issue(listIssue, strField, "Snippet key must be a string.")
                continue

            if strSnippetKey in setExcludedSnippet:
                add_issue(listIssue, strField, f"Duplicate excluded AST Snippet key: {strSnippetKey!r}.")
                continue

            if (
                _parse_component_snippet_key(
                    snippetKey=strSnippetKey,
                    packageName=manifestObj.packageName,
                    publicModuleNameSet=setPublicModuleName,
                    field=strField,
                    issueList=listIssue,
                    requireExistingModule=False,
                )
                is None
            ):
                continue

            setExcludedSnippet.add(strSnippetKey)

    dictOverrideValue = value.get("astSnippetOverrides")
    dictOverride: dict[str, DictAstSnippetOverride] = {}

    if not isinstance(dictOverrideValue, dict):
        add_issue(listIssue, "astSnippetOverrides", "Value must be an object.")
    else:
        for strSnippetKey, dictOverrideItem in dictOverrideValue.items():
            strField = f"astSnippetOverrides.{strSnippetKey}"

            if not isinstance(strSnippetKey, str):
                add_issue(listIssue, "astSnippetOverrides", "Every Snippet key must be a string.")
                continue

            if strSnippetKey in setExcludedSnippet:
                add_issue(
                    listIssue,
                    strField,
                    "An excluded AST Snippet cannot also have an override.",
                )
                continue

            if strSnippetKey not in astSnippets["snippets"]:
                add_issue(listIssue, strField, "The AST-generated Snippet does not exist.")
                continue

            dictNormalizedOverride = _normalize_override(
                value=dictOverrideItem,
                field=strField,
                availableImportOrder=dictAvailableImportOrder,
                issueList=listIssue,
            )
            if dictNormalizedOverride is not None:
                dictOverride[strSnippetKey] = dictNormalizedOverride

    dictHandWrittenValue = value.get("snippets")
    dictHandWrittenSnippet: dict[str, DictNormalizedSnippet] = {}

    if not isinstance(dictHandWrittenValue, dict):
        add_issue(listIssue, "snippets", "Value must be an object.")
    else:
        for strSnippetKey, dictSnippetItem in dictHandWrittenValue.items():
            if not isinstance(strSnippetKey, str):
                add_issue(listIssue, "snippets", "Every Snippet key must be a string.")
                continue

            if strSnippetKey in astSnippets["snippets"]:
                add_issue(
                    listIssue,
                    f"snippets.{strSnippetKey}",
                    (
                        "A hand-written Snippet cannot use an AST-generated Snippet key. "
                        "Use astSnippetOverrides to customize the AST-generated Snippet."
                    ),
                )
                continue

            dictNormalizedSnippet = _normalize_hand_written_snippet(
                snippetKey=strSnippetKey,
                value=dictSnippetItem,
                packageName=manifestObj.packageName,
                publicModuleNameSet=setPublicModuleName,
                availableImportOrder=dictAvailableImportOrder,
                issueList=listIssue,
            )
            if dictNormalizedSnippet is not None:
                dictHandWrittenSnippet[strSnippetKey] = dictNormalizedSnippet

    raise_config_issues(listIssue)

    listWarning: list[DictSnippetConfigWarning] = []
    for strSnippetKey in sorted(setExcludedSnippet - set(astSnippets["snippets"])):
        # Users have configured excluded snippets, but these snippets have no related functions.
        listWarning.append({
            "code": "excluded_ast_snippet_missing",
            "snippetKey": strSnippetKey,
            "message": f"Excluded AST Snippet no longer exists: {strSnippetKey}",
        })

    dictFinalSnippet: dict[str, DictNormalizedSnippet] = {}

    for strSnippetKey, dictAstSnippet in astSnippets["snippets"].items():
        if strSnippetKey in setExcludedSnippet:
            continue

        dictSnippet = deepcopy(dictAstSnippet)
        dictSnippetOverride = dictOverride.get(strSnippetKey)

        if dictSnippetOverride is not None:
            if "label" in dictSnippetOverride:
                dictSnippet["label"] = dictSnippetOverride["label"]

            if "description" in dictSnippetOverride:
                dictSnippet["description"] = dictSnippetOverride["description"]

            if "insertionMode" in dictSnippetOverride:
                dictSnippet["insertionMode"] = dictSnippetOverride["insertionMode"]

            bodyValue = dictSnippetOverride.get("body", dictSnippet["body"])
            listBody = _normalize_snippet_body(
                value=bodyValue,
                insertionMode=dictSnippet["insertionMode"],
                field=f"astSnippetOverrides.{strSnippetKey}.body",
                issueList=[],
            )
            assert listBody is not None
            dictSnippet["body"] = listBody

            dictSnippet["imports"] = _merge_imports(
                mandatoryImports=dictAstSnippet["imports"],
                additionalImports=dictSnippetOverride.get("imports", {}),
                availableImportOrder=dictAvailableImportOrder,
            )

        dictFinalSnippet[strSnippetKey] = dictSnippet

    dictFinalSnippet.update(dictHandWrittenSnippet)

    dictLabelOwner: dict[tuple[str, str], str] = {}
    dictPrefixOwner: dict[str, str] = {}
    listConflictIssue: list[dict[str, object]] = []

    for strSnippetKey, dictSnippetItem in dictFinalSnippet.items():
        tupleLabelKey = (dictSnippetItem["category"], dictSnippetItem["label"])
        strExistingLabelOwner = dictLabelOwner.get(tupleLabelKey)
        if strExistingLabelOwner is not None:
            add_issue(
                listConflictIssue,
                f"snippets.{strSnippetKey}.label",
                f"Duplicate label in category {dictSnippetItem['category']!r}; "
                f"it is already used by {strExistingLabelOwner!r}.",
            )
        else:
            dictLabelOwner[tupleLabelKey] = strSnippetKey

        strPrefix = dictSnippetItem["prefix"]
        strExistingPrefixOwner = dictPrefixOwner.get(strPrefix)
        if strExistingPrefixOwner is not None:
            add_issue(
                listConflictIssue,
                f"snippets.{strSnippetKey}.prefix",
                f"Duplicate Snippet prefix; it is already used by {strExistingPrefixOwner!r}.",
            )
        else:
            dictPrefixOwner[strPrefix] = strSnippetKey

    raise_config_issues(listConflictIssue)

    listCategoryOrder = [
        f"{manifestObj.packageName}_{moduleName}"
        for moduleName in listPublicModuleName
        if any(
            snippetItem["category"] == f"{manifestObj.packageName}_{moduleName}"
            for snippetItem in dictFinalSnippet.values()
        )
    ]

    dictStableSnippet: dict[str, DictNormalizedSnippet] = {}
    for strCategory in listCategoryOrder:
        for strSnippetKey in sorted(
            key for key, dictItem in dictFinalSnippet.items() if dictItem["category"] == strCategory
        ):
            dictStableSnippet[strSnippetKey] = _stabilize_snippet(dictFinalSnippet[strSnippetKey])

    dictImportSource: dict[str, DictImportSourceConfig] = {
        manifestObj.packageName: {
            "order": listPublicModuleName,
            "aliasMode": "source_module",
        }
    }

    return _SnippetCatalogBuildResult(
        catalog={
            "schemaVersion": 1,
            "categoryOrder": listCategoryOrder,
            "importSources": dictImportSource,
            "snippets": dictStableSnippet,
        },
        warnings=listWarning,
        # Count only exclusions that match current AST-generated Snippets.
        excludedCount=len(setExcludedSnippet & set(astSnippets["snippets"])),
        handWrittenCount=len(dictHandWrittenSnippet),
    )
