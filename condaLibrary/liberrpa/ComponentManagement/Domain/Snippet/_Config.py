# FileName: _Config.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import read_jsonc, write_text_atomic
from liberrpa.ComponentManagement.Common._Validation import (
    add_validation_issue,
    validate_json_object_fields,
)
from liberrpa.ComponentManagement.Types._Warning import (
    DictComponentManagementWarning_SnippetConfig,
)
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Snippet import (
    Str_SnippetInsertionMode,
    DictSnippet_Imports,
    DictSnippet_Normalized,
    DictSnippet_AstFile,
    DictSnippet_ImportSourceConfig,
    DictSnippet_CatalogFile,
    DictSnippet_AstOverride,
)

from pathlib import Path
from copy import deepcopy
import keyword
from dataclasses import dataclass


_PATH_TEMPLATE = Path(__file__).resolve().parent / "Templates/snippets.jsonc.template"


_SET_ALLOWED_KEYS_SNIPPET_CONFIG = {
    # snippets.jsonc.template has the four keys only.
    "schemaVersion",
    "excludedAstSnippets",
    "astSnippetOverrides",
    "snippets",
}
_SET_ALLOWED_KEYS_AST_SNIPPET_OVERRIDE = {
    "label",
    "body",
    "description",
    "insertionMode",
    "imports",
}
_SET_ALLOWED_KEYS_HAND_WRITTEN_SNIPPET = {
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
    catalog: DictSnippet_CatalogFile
    warnings: list[DictComponentManagementWarning_SnippetConfig]
    excludedCount: int
    handWrittenCount: int


def _validate_single_line_string(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    """Validate a non-empty single-line Snippet label or prefix."""
    if not isinstance(value, str) or value.strip() == "":
        add_validation_issue(issueList, field, "Value must be a non-empty string.")
        return None

    if "\r" in value or "\n" in value:
        add_validation_issue(issueList, field, "Value must be a single line.")
        return None

    return value


def _normalize_description(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> str | None:
    if not isinstance(value, str) or value.strip() == "":
        add_validation_issue(issueList, field, "Value must be a non-empty string.")
        return None

    return value


def _validate_insertion_mode(
    value: object,
    field: str,
    issueList: list[dict[str, object]],
) -> Str_SnippetInsertionMode | None:
    if value == "line":
        return "line"

    if value == "cursor":
        return "cursor"

    add_validation_issue(issueList, field, 'Value must be either "line" or "cursor".')
    return None


def _parse_snippet_body(
    value: object,
    insertionMode: Str_SnippetInsertionMode,
    field: str,
    issueList: list[dict[str, object]],
) -> list[str] | None:
    if isinstance(value, str):
        listBodyLine = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        listBodyLine = list(value)
    else:
        add_validation_issue(issueList, field, "Value must be a string or a list of strings.")
        return None

    if not listBodyLine or all(line.strip() == "" for line in listBodyLine):
        add_validation_issue(issueList, field, "Snippet body cannot be empty.")
        return None

    if insertionMode == "line":
        if listBodyLine[-1] == "":
            listBodyLine[-1] = "$0"
        elif listBodyLine[-1] != "$0":
            listBodyLine.append("$0")
        else:
            pass

    return listBodyLine


def _parse_imports(
    value: object,
    field: str,
    availableImportOrderDict: dict[str, tuple[str, ...]],
    issueList: list[dict[str, object]],
) -> DictSnippet_Imports | None:
    if not isinstance(value, dict):
        add_validation_issue(
            issueList,
            field,
            "Value must be an object containing import source and name-list pairs.",
        )
        return None

    dictResult: DictSnippet_Imports = {}

    for importSource, importNameValue in value.items():
        strImportField = f"{field}.{importSource}"

        if not isinstance(importSource, str) or importSource == "":
            add_validation_issue(issueList, field, "Every import source must be a non-empty string.")
            continue

        if importSource not in availableImportOrderDict:
            add_validation_issue(
                issueList,
                strImportField,
                f"Import source is not available to this Component Snippet: {importSource!r}.",
            )
            continue

        if not isinstance(importNameValue, list) or not importNameValue:
            add_validation_issue(issueList, strImportField, "Import names must be a non-empty list.")
            continue

        listImportName: list[str] = []
        setImportName: set[str] = set()

        for importName in importNameValue:
            if (
                not isinstance(importName, str)
                or not importName.isidentifier()
                or keyword.iskeyword(importName)
            ):
                add_validation_issue(
                    issueList,
                    strImportField,
                    f"Import name must be a valid non-keyword Python identifier: {importName!r}.",
                )
                continue

            if importName in setImportName:
                add_validation_issue(
                    issueList, strImportField, f"Duplicate import name: {importName!r}."
                )
                continue

            setImportName.add(importName)
            listImportName.append(importName)

        tupleImportOrder = availableImportOrderDict[importSource]
        dictImportIndex = {name: index for index, name in enumerate(tupleImportOrder)}
        listUnknownImportName = sorted(
            name for name in listImportName if name not in dictImportIndex
        )

        if listUnknownImportName:
            add_validation_issue(
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
    availableImportOrderDict: dict[str, tuple[str, ...]],
    issueList: list[dict[str, object]],
) -> DictSnippet_AstOverride | None:
    if not isinstance(value, dict):
        add_validation_issue(issueList, field, "Value must be an object.")
        return None

    validate_json_object_fields(
        value,
        _SET_ALLOWED_KEYS_AST_SNIPPET_OVERRIDE,
        field,
        issueList,
    )
    dictResult: DictSnippet_AstOverride = {}

    if "label" in value:
        strLabel = _validate_single_line_string(
            value["label"], f"{field}.label", issueList
        )
        if strLabel is not None:
            dictResult["label"] = strLabel

    if "description" in value:
        strDescription = _normalize_description(
            value["description"], f"{field}.description", issueList
        )
        if strDescription is not None:
            dictResult["description"] = strDescription

    insertionMode: Str_SnippetInsertionMode | None = None
    if "insertionMode" in value:
        insertionMode = _validate_insertion_mode(
            value["insertionMode"], f"{field}.insertionMode", issueList
        )
        if insertionMode is not None:
            dictResult["insertionMode"] = insertionMode

    if "body" in value:
        bodyInsertionMode: Str_SnippetInsertionMode = insertionMode or "line"
        listBody = _parse_snippet_body(
            value["body"], bodyInsertionMode, f"{field}.body", issueList
        )
        if listBody is not None:
            dictResult["body"] = listBody

    if "imports" in value:
        dictImports = _parse_imports(
            value["imports"], f"{field}.imports", availableImportOrderDict, issueList
        )
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

    if (
        strSeparator == ""
        or "." in strSnippetName
        or not strCategory.startswith(strCategoryPrefix)
    ):
        add_validation_issue(
            issueList,
            field,
            f"Snippet key must use {packageName}_ModuleName.snippet_name.",
        )
        return None

    strModuleName = strCategory[len(strCategoryPrefix) :]
    if strModuleName == "":
        add_validation_issue(
            issueList, field, "Snippet key must contain a public Component Module name."
        )
        return None

    if not strModuleName.isidentifier() or keyword.iskeyword(strModuleName):
        add_validation_issue(
            issueList,
            field,
            f"Module name must be a valid non-keyword Python identifier: {strModuleName!r}.",
        )
        return None

    if requireExistingModule and strModuleName not in publicModuleNameSet:
        add_validation_issue(
            issueList, field, f"Public Component Module was not found: {strModuleName!r}."
        )
        return None

    if not strSnippetName.isidentifier() or keyword.iskeyword(strSnippetName):
        add_validation_issue(
            issueList,
            field,
            f"Snippet name must be a valid non-keyword Python identifier: {strSnippetName!r}.",
        )
        return None

    return strCategory, strModuleName, strSnippetName


def _merge_imports(
    mandatoryImportDict: DictSnippet_Imports,
    additionalImportDict: DictSnippet_Imports,
    availableImportOrderDict: dict[str, tuple[str, ...]],
) -> DictSnippet_Imports:
    dictMergedImport: dict[str, set[str]] = {}

    for imports in (mandatoryImportDict, additionalImportDict):
        for importSource, listImportName in imports.items():
            dictMergedImport.setdefault(importSource, set()).update(listImportName)

    dictResult: DictSnippet_Imports = {}

    for importSource in sorted(dictMergedImport):
        dictImportIndex = {
            name: index
            for index, name in enumerate(availableImportOrderDict[importSource])
        }
        dictResult[importSource] = sorted(
            dictMergedImport[importSource],
            key=dictImportIndex.__getitem__,
        )

    return dictResult


def _normalize_hand_written_snippet(
    snippetKey: str,
    snippetValue: object,
    packageName: str,
    publicModuleNameSet: set[str],
    availableImportOrderDict: dict[str, tuple[str, ...]],
    issueList: list[dict[str, object]],
) -> DictSnippet_Normalized | None:
    strField = f"snippets.{snippetKey}"
    tupleKeyPart = _parse_component_snippet_key(
        snippetKey=snippetKey,
        packageName=packageName,
        publicModuleNameSet=publicModuleNameSet,
        field=strField,
        issueList=issueList,
        requireExistingModule=True,
    )

    if not isinstance(snippetValue, dict):
        add_validation_issue(issueList, strField, "Value must be an object.")
        return None

    validate_json_object_fields(
        snippetValue,
        _SET_ALLOWED_KEYS_HAND_WRITTEN_SNIPPET,
        strField,
        issueList,
    )

    if tupleKeyPart is None:
        return None

    strCategory, strModuleName, strSnippetName = tupleKeyPart

    strPrefix = snippetKey
    if "prefix" in snippetValue:
        normalizedPrefix = _validate_single_line_string(
            snippetValue["prefix"], f"{strField}.prefix", issueList
        )
        if normalizedPrefix is not None:
            strPrefix = normalizedPrefix

    strLabel = strSnippetName
    if "label" in snippetValue:
        normalizedLabel = _validate_single_line_string(
            snippetValue["label"], f"{strField}.label", issueList
        )
        if normalizedLabel is not None:
            strLabel = normalizedLabel

    insertionMode: Str_SnippetInsertionMode = "line"
    if "insertionMode" in snippetValue:
        normalizedInsertionMode = _validate_insertion_mode(
            snippetValue["insertionMode"],
            f"{strField}.insertionMode",
            issueList,
        )
        if normalizedInsertionMode is not None:
            insertionMode = normalizedInsertionMode

    if "body" not in snippetValue:
        add_validation_issue(issueList, strField, "Missing required field: body.")
        listBody = None
    else:
        listBody = _parse_snippet_body(
            snippetValue["body"], insertionMode, f"{strField}.body", issueList
        )

    if "description" not in snippetValue:
        add_validation_issue(issueList, strField, "Missing required field: description.")
        strDescription = None
    else:
        strDescription = _normalize_description(
            snippetValue["description"], f"{strField}.description", issueList
        )

    dictAdditionalImport: DictSnippet_Imports = {}
    if "imports" in snippetValue:
        normalizedImports = _parse_imports(
            snippetValue["imports"],
            f"{strField}.imports",
            availableImportOrderDict,
            issueList,
        )
        if normalizedImports is not None:
            dictAdditionalImport = normalizedImports

    # Ensure all errors have been added, then return.
    if listBody is None or strDescription is None:
        return None

    dictMandatoryImport: DictSnippet_Imports = {packageName: [strModuleName]}

    return {
        "category": strCategory,
        "label": strLabel,
        "prefix": strPrefix,
        "body": listBody,
        "description": strDescription,
        "insertionMode": insertionMode,
        "imports": _merge_imports(
            mandatoryImportDict=dictMandatoryImport,
            additionalImportDict=dictAdditionalImport,
            availableImportOrderDict=availableImportOrderDict,
        ),
    }


def _stabilize_snippet(snippetDict: DictSnippet_Normalized) -> DictSnippet_Normalized:
    # Ensure items in snippetDict have a proper order for Git.
    return {
        "category": snippetDict["category"],
        "label": snippetDict["label"],
        "prefix": snippetDict["prefix"],
        "body": list(snippetDict["body"]),
        "description": snippetDict["description"],
        "insertionMode": snippetDict["insertionMode"],
        "imports": {
            importSource: list(importName)
            for importSource, importName in snippetDict["imports"].items()
        },
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
            message=f"Unexpected internal error: The Component Snippet template is empty: {_PATH_TEMPLATE}",
        )

    try:
        write_text_atomic(path=configPath, text=strTemplate.rstrip("\r\n") + "\n")
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to create Component Snippet configuration: {configPath}",
        ) from e

    return True


def _raise_config_issues(issueList: list[dict[str, object]]) -> None:
    if not issueList:
        return

    raise ComponentManagementError(
        code="snippet_config_invalid",
        message="Invalid Component Snippet configuration.",
        details={"issues": issueList},
    )


def build_snippet_catalog(
    configPath: Path,
    astSnippetDict: DictSnippet_AstFile,
    packagePath: Path,
    manifestObj: Info_ProjectManifest_Component,
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
            details={
                "issues": [
                    {
                        "field": "snippets.jsonc",
                        "message": "The root value must be an object.",
                    }
                ]
            },
        )

    listIssue: list[dict[str, object]] = []
    validate_json_object_fields(
        value,
        _SET_ALLOWED_KEYS_SNIPPET_CONFIG,
        "snippets.jsonc",
        listIssue,
    )

    schemaVersionValue = value.get("schemaVersion")
    if type(schemaVersionValue) is not int or schemaVersionValue != 1:
        add_validation_issue(listIssue, "schemaVersion", "Only schemaVersion 1 is supported.")

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
        add_validation_issue(
            listIssue, "excludedAstSnippets", "Value must be a list of Snippet keys."
        )
    else:
        for intIndex, strSnippetKey in enumerate(listExcludedValue):
            strField = f"excludedAstSnippets[{intIndex}]"

            if not isinstance(strSnippetKey, str):
                add_validation_issue(listIssue, strField, "Snippet key must be a string.")
                continue

            if strSnippetKey in setExcludedSnippet:
                add_validation_issue(
                    listIssue,
                    strField,
                    f"Duplicate excluded AST Snippet key: {strSnippetKey!r}.",
                )
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
    dictOverride: dict[str, DictSnippet_AstOverride] = {}
    if not isinstance(dictOverrideValue, dict):
        add_validation_issue(listIssue, "astSnippetOverrides", "Value must be an object.")
    else:
        for strSnippetKey, dictOverrideItem in dictOverrideValue.items():
            strField = f"astSnippetOverrides.{strSnippetKey}"

            if not isinstance(strSnippetKey, str):
                add_validation_issue(
                    listIssue,
                    "astSnippetOverrides",
                    "Every Snippet key must be a string.",
                )
                continue

            if strSnippetKey in setExcludedSnippet:
                add_validation_issue(
                    listIssue,
                    strField,
                    "An excluded AST Snippet cannot also have an override.",
                )
                continue

            if strSnippetKey not in astSnippetDict["snippets"]:
                add_validation_issue(
                    listIssue, strField, "The AST-generated Snippet does not exist."
                )
                continue

            dictNormalizedOverride = _normalize_override(
                value=dictOverrideItem,
                field=strField,
                availableImportOrderDict=dictAvailableImportOrder,
                issueList=listIssue,
            )
            if dictNormalizedOverride is not None:
                dictOverride[strSnippetKey] = dictNormalizedOverride

    dictHandWrittenValue = value.get("snippets")
    dictHandWrittenSnippet: dict[str, DictSnippet_Normalized] = {}
    if not isinstance(dictHandWrittenValue, dict):
        add_validation_issue(listIssue, "snippets", "Value must be an object.")
    else:
        for strSnippetKey, dictSnippetItem in dictHandWrittenValue.items():
            if not isinstance(strSnippetKey, str):
                add_validation_issue(listIssue, "snippets", "Every Snippet key must be a string.")
                continue

            if strSnippetKey in astSnippetDict["snippets"]:
                add_validation_issue(
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
                snippetValue=dictSnippetItem,
                packageName=manifestObj.packageName,
                publicModuleNameSet=setPublicModuleName,
                availableImportOrderDict=dictAvailableImportOrder,
                issueList=listIssue,
            )
            if dictNormalizedSnippet is not None:
                dictHandWrittenSnippet[strSnippetKey] = dictNormalizedSnippet

    _raise_config_issues(listIssue)

    listWarning: list[DictComponentManagementWarning_SnippetConfig] = []
    for strSnippetKey in sorted(setExcludedSnippet - set(astSnippetDict["snippets"])):
        # Users have configured excluded snippets, but these snippets have no related functions.
        listWarning.append({
            "code": "excluded_ast_snippet_missing",
            "message": f"Excluded AST Snippet no longer exists: {strSnippetKey}",
            "snippetKey": strSnippetKey,
        })

    dictAggregateSnippet: dict[str, DictSnippet_Normalized] = {}

    for strSnippetKey, dictAstSnippet in astSnippetDict["snippets"].items():
        if strSnippetKey in setExcludedSnippet:
            continue

        dictSnippet = deepcopy(dictAstSnippet)
        dictSnippetOverride = dictOverride.get(strSnippetKey)

        if dictSnippetOverride is not None:
            dictSnippet["label"] = dictSnippetOverride.get("label", dictSnippet["label"])
            dictSnippet["description"] = dictSnippetOverride.get(
                "description", dictSnippet["description"]
            )
            dictSnippet["insertionMode"] = dictSnippetOverride.get(
                "insertionMode", dictSnippet["insertionMode"]
            )

            bodyValue = dictSnippetOverride.get("body", dictSnippet["body"])
            listBody = _parse_snippet_body(
                value=bodyValue,
                insertionMode=dictSnippet["insertionMode"],
                field=f"astSnippetOverrides.{strSnippetKey}.body",
                issueList=[],
            )
            assert listBody is not None
            dictSnippet["body"] = listBody

            dictSnippet["imports"] = _merge_imports(
                mandatoryImportDict=dictAstSnippet["imports"],
                additionalImportDict=dictSnippetOverride.get("imports", {}),
                availableImportOrderDict=dictAvailableImportOrder,
            )

        dictAggregateSnippet[strSnippetKey] = dictSnippet

    dictAggregateSnippet.update(dictHandWrittenSnippet)

    dictLabelOwner: dict[tuple[str, str], str] = {}
    dictPrefixOwner: dict[str, str] = {}
    listConflictIssue: list[dict[str, object]] = []

    for strSnippetKey, dictSnippetItem in dictAggregateSnippet.items():
        tupleLabelKey = (dictSnippetItem["category"], dictSnippetItem["label"])
        strExistingLabelOwner = dictLabelOwner.get(tupleLabelKey)
        if strExistingLabelOwner is not None:
            add_validation_issue(
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
            add_validation_issue(
                listConflictIssue,
                f"snippets.{strSnippetKey}.prefix",
                f"Duplicate Snippet prefix; it is already used by {strExistingPrefixOwner!r}.",
            )
        else:
            dictPrefixOwner[strPrefix] = strSnippetKey

    _raise_config_issues(listConflictIssue)

    listCategoryOrder = [
        f"{manifestObj.packageName}_{moduleName}"
        for moduleName in listPublicModuleName
        if any(
            snippetItem["category"] == f"{manifestObj.packageName}_{moduleName}"
            for snippetItem in dictAggregateSnippet.values()
        )
    ]

    dictStableSnippet: dict[str, DictSnippet_Normalized] = {}
    for strCategory in listCategoryOrder:
        for strSnippetKey in sorted(
            key
            for key, dictItem in dictAggregateSnippet.items()
            if dictItem["category"] == strCategory
        ):
            dictStableSnippet[strSnippetKey] = _stabilize_snippet(
                dictAggregateSnippet[strSnippetKey]
            )

    dictImportSource: dict[str, DictSnippet_ImportSourceConfig] = {
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
        excludedCount=len(setExcludedSnippet & set(astSnippetDict["snippets"])),
        handWrittenCount=len(dictHandWrittenSnippet),
    )
