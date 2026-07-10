# FileName: GenerateApiData.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Generate structured API metadata for LiberRPA snippet and API documentation tools."""

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any, NotRequired, TypedDict, get_overloads

from ApiConfig import (
    PUBLIC_MODULE_ORDER,
    SKIP_FUNCTIONS,
)
from SnippetUtils import find_project_root, get_snippets_dir, write_json, get_snippet_choices


class DictParameterInfo(TypedDict):
    name: str
    kind: str
    required: bool
    default: str | None
    annotation: str | None
    snippetChoices: NotRequired[list[str]]


class DictOverloadInfo(TypedDict):
    signature: str
    returnAnnotation: str | None
    parameters: list[DictParameterInfo]


class DictApiItem(TypedDict):
    module: str
    name: str
    title: str
    prefix: str
    description: str
    returnAnnotation: str | None
    hasReturnValue: bool
    parameters: list[DictParameterInfo]
    overloads: list[DictOverloadInfo]


def _is_overload_decorator(decorator: ast.expr) -> bool:
    """Return True if an AST decorator expression refers to typing.overload."""
    if isinstance(decorator, ast.Name):
        return decorator.id == "overload"

    if isinstance(decorator, ast.Attribute):
        return decorator.attr == "overload"

    return False


def _is_overload_function_def(node: ast.FunctionDef) -> bool:
    """Return True if a function definition is an @overload variant."""
    return any(_is_overload_decorator(decorator) for decorator in node.decorator_list)


def _get_public_function_names_in_order(filePath: Path) -> list[str]:
    """Read a module source file and return top-level public implementation function names in source order."""
    tree = ast.parse(filePath.read_text(encoding="utf-8"), filename=str(filePath))

    result: list[str] = []
    seen: set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        if _is_overload_function_def(node):
            continue
        if node.name in seen:
            raise ValueError(f"Duplicate public implementation function found in {filePath}: {node.name}")

        seen.add(node.name)
        result.append(node.name)

    return result


def _annotation_to_str(annotation: object) -> str | None:
    if annotation is inspect.Signature.empty:
        return None
    if annotation is None:
        return None
    return str(annotation)


def _default_to_str(default: object) -> str | None:
    if default is inspect.Parameter.empty:
        return None
    if default is Ellipsis:
        return "..."
    return repr(default)


def _build_parameter_info(parameter: inspect.Parameter) -> DictParameterInfo:
    result: DictParameterInfo = {
        "name": parameter.name,
        "kind": parameter.kind.name,
        "required": parameter.default is inspect.Parameter.empty,
        "default": _default_to_str(parameter.default),
        "annotation": _annotation_to_str(parameter.annotation),
    }

    snippetChoices = get_snippet_choices(parameter)
    if snippetChoices:
        result["snippetChoices"] = snippetChoices

    return result


def _signature_to_str(funcName: str, signature: inspect.Signature) -> str:
    """Return a readable function signature string for API documentation."""
    signatureText = str(signature).replace(" = Ellipsis", " = ...")
    return f"{funcName}{signatureText}"


def _build_overload_info(funcName: str, func: Any) -> DictOverloadInfo:
    signature = inspect.signature(func)

    if signature.return_annotation is inspect.Signature.empty:
        raise ValueError(f"Overload signature {funcName} is missing return annotation.")

    return {
        "signature": _signature_to_str(funcName=funcName, signature=signature),
        "returnAnnotation": _annotation_to_str(signature.return_annotation),
        "parameters": [_build_parameter_info(parameter) for parameter in signature.parameters.values()],
    }


def _build_api_item(moduleName: str, funcName: str, func: Any) -> DictApiItem:
    signature = inspect.signature(func)

    if signature.return_annotation is inspect.Signature.empty:
        raise ValueError(f"{moduleName}.{funcName} is missing return annotation.")

    returnAnnotation = _annotation_to_str(signature.return_annotation)
    hasReturnValue = signature.return_annotation is not None
    overloads = [_build_overload_info(funcName=funcName, func=overloadFunc) for overloadFunc in get_overloads(func)]

    return {
        "module": moduleName,
        "name": funcName,
        "title": f"{moduleName}.{funcName}",
        "prefix": f"{moduleName}.{funcName}",
        "description": inspect.getdoc(func) or "",
        "returnAnnotation": returnAnnotation,
        "hasReturnValue": hasReturnValue,
        "parameters": [_build_parameter_info(parameter) for parameter in signature.parameters.values()],
        "overloads": overloads,
    }


def generate_api_manifest() -> list[DictApiItem]:
    root = find_project_root()
    manifest: list[DictApiItem] = []

    for moduleName in PUBLIC_MODULE_ORDER:
        moduleFile = root / "liberrpa" / f"{moduleName}.py"
        if not moduleFile.is_file():
            raise FileNotFoundError(f"Module source file was not found: {moduleFile}")

        functionNames = _get_public_function_names_in_order(moduleFile)
        functionNames = [name for name in functionNames if name not in SKIP_FUNCTIONS.get(moduleName, set())]

        moduleObj = importlib.import_module(f"liberrpa.{moduleName}")

        for funcName in functionNames:
            func = getattr(moduleObj, funcName, None)
            if func is None:
                raise AttributeError(f"Function exists in source but was not found at runtime: {moduleName}.{funcName}")
            manifest.append(_build_api_item(moduleName=moduleName, funcName=funcName, func=func))

    return manifest


def main() -> None:
    snippetsDir = get_snippets_dir()

    apiManifest = generate_api_manifest()
    write_json(snippetsDir / "api_manifest.json", apiManifest)


if __name__ == "__main__":
    main()
