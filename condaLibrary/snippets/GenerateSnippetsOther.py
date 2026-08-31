# FileName: GenerateSnippetsOther.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Generate VS Code snippets for public liberrpa API functions."""

from typing import cast

from ApiConfig import (
    DictSnippetsItem,
    MANAGED_IMPORT_SOURCE,
    PARAMETER_PLACEHOLDER_NAMES,
    PUBLIC_MODULE_ORDER,
    RETURN_PLACEHOLDER_BY_ANNOTATION,
    SPECIAL_SNIPPETS,
)
from GenerateApiData import DictApiItem, DictParameterInfo, generate_api_manifest
from SnippetUtils import get_snippets_dir, read_json, write_json, format_snippet_choice


def _load_or_generate_api_manifest() -> list[DictApiItem]:
    manifestPath = get_snippets_dir() / "api_manifest.json"
    if manifestPath.is_file():
        return cast(list[DictApiItem], read_json(manifestPath, list))
    return generate_api_manifest()


_NONE_RETURN_ANNOTATION = {
    "None",
    "NoneType",
    "<class 'NoneType'>",
}

_CONTAINER_RETURN_PLACEHOLDER = {
    "list": "listResult",
    "dict": "dictResult",
    "tuple": "tupleResult",
    "set": "setResult",
}


def _split_top_level_union(annotation: str) -> list[str]:
    listPart: list[str] = []
    intDepth = 0
    intStart = 0

    for intIndex, strChar in enumerate(annotation):
        if strChar in "[({":
            intDepth += 1
            continue

        if strChar in "])}":
            intDepth -= 1
            continue

        if strChar == "|" and intDepth == 0:
            listPart.append(annotation[intStart:intIndex].strip())
            intStart = intIndex + 1

    if not listPart:
        return [annotation.strip()]

    listPart.append(annotation[intStart:].strip())
    return listPart


def _get_annotation_return_placeholder(returnAnnotation: str) -> str:
    returnAnnotation = returnAnnotation.strip()

    placeholder = RETURN_PLACEHOLDER_BY_ANNOTATION.get(returnAnnotation)
    if placeholder is not None:
        return placeholder

    listUnionPart = _split_top_level_union(returnAnnotation)

    if len(listUnionPart) > 1:
        listNonNonePart = [
            part for part in listUnionPart if part not in _NONE_RETURN_ANNOTATION
        ]

        setPlaceholder = {
            _get_annotation_return_placeholder(part) for part in listNonNonePart
        }

        if len(setPlaceholder) == 1:
            return next(iter(setPlaceholder))

        return "result"

    annotationLower = returnAnnotation.lower().removeprefix("typing.")

    for strTypeName, strPlaceholder in _CONTAINER_RETURN_PLACEHOLDER.items():
        if annotationLower == strTypeName or annotationLower.startswith(
            f"{strTypeName}["
        ):
            return strPlaceholder

    if annotationLower.startswith("literal["):
        return "strResult"

    return "result"


def _get_return_placeholder(returnAnnotation: str | None, item: DictApiItem) -> str:

    # As a safety net.
    if returnAnnotation is None:
        raise ValueError(
            "returnAnnotation should not be None when hasReturnValue is True."
        )

    listOverloadReturnAnnotation = [
        overload["returnAnnotation"]
        for overload in item.get("overloads", [])
        if overload["returnAnnotation"] is not None
    ]

    if not listOverloadReturnAnnotation:
        return _get_annotation_return_placeholder(returnAnnotation)

    setPlaceholder = {
        _get_annotation_return_placeholder(annotation)
        for annotation in listOverloadReturnAnnotation
    }

    if len(setPlaceholder) == 1:
        return next(iter(setPlaceholder))

    return "result"


def _format_parameter_placeholder(parameter: DictParameterInfo, index: int) -> str:
    name = parameter["name"]
    kind = parameter["kind"]

    # As a safety net. Only Logging module has these kinds of arguments but they are generated manually.
    if kind == "VAR_POSITIONAL":
        return f"*${{{index}:{name}}}"
    if kind == "VAR_KEYWORD":
        return f"**${{{index}:{name}}}"

    snippetChoices = parameter.get("snippetChoices")
    if snippetChoices:
        return f"{name}={format_snippet_choice(index=index, choices=snippetChoices)}"

    if parameter["required"]:
        placeholder = PARAMETER_PLACEHOLDER_NAMES.get(name)
        if placeholder is not None:
            return f"{name}=${{{index}:{placeholder}}}"
        return f"{name}=${index}"

    default = parameter["default"]
    return f"{name}=${{{index}:{default}}}"


def _build_body(item: DictApiItem) -> str:
    index = 1
    returnPart = ""

    if item["hasReturnValue"]:
        placeholder = _get_return_placeholder(item["returnAnnotation"], item=item)
        returnPart = f"${{{index}:{placeholder}}} = "
        index += 1

    parameters = [
        _format_parameter_placeholder(parameter, idx + index)
        for idx, parameter in enumerate(item["parameters"])
    ]
    paramsText = ", ".join(parameters)
    return f"{returnPart}{item['module']}.{item['name']}({paramsText})"


def _build_generated_snippet(item: DictApiItem) -> DictSnippetsItem:
    return {
        "prefix": item["prefix"],
        "body": _build_body(item),
        "description": item["description"],
        "imports": {MANAGED_IMPORT_SOURCE: [item["module"]]},
    }


def _generate_snippets(
    apiManifest: list[DictApiItem],
) -> dict[str, dict[str, DictSnippetsItem]]:
    """Generate snippet groups in PUBLIC_MODULE_ORDER."""
    manifestByModule: dict[str, list[DictApiItem]] = {}
    for item in apiManifest:
        manifestByModule.setdefault(item["module"], []).append(item)

    dictSnippets: dict[str, dict[str, DictSnippetsItem]] = {}

    for moduleName in PUBLIC_MODULE_ORDER:
        moduleSnippets: dict[str, DictSnippetsItem] = {}

        for title, snippet in SPECIAL_SNIPPETS.get(moduleName, {}).items():
            moduleSnippets[title] = cast(DictSnippetsItem, snippet)

        for item in manifestByModule.get(moduleName, []):
            moduleSnippets[item["title"]] = _build_generated_snippet(item)

        if moduleSnippets:
            dictSnippets[moduleName] = moduleSnippets

    # Make unexpected modules visible instead of silently dropping them.
    unexpectedModules = sorted(set(manifestByModule) - set(PUBLIC_MODULE_ORDER))
    if unexpectedModules:
        raise ValueError(f"Unexpected modules in API manifest: {unexpectedModules}")

    return dictSnippets


def main() -> None:
    snippetsDir = get_snippets_dir()
    apiManifest = _load_or_generate_api_manifest()
    dictSnippets = _generate_snippets(apiManifest=apiManifest)
    write_json(snippetsDir / "snippets_other.snippets", dictSnippets)


if __name__ == "__main__":
    main()
