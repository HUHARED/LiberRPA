# FileName: _Ast.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Types._Warning import (
    DictComponentManagementWarning_SnippetDiagnostic,
)
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Snippet import (
    DictSnippet_Normalized,
    DictSnippet_AstFile,
)

from pathlib import Path

import ast
import re
import tokenize
import keyword

_REGEX_COMPONENT_MODULE_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")


class _FunctionReturnVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.hasReturnValue = False

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            self.hasReturnValue = True

    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return None

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return None

    def visit_Yield(self, _node: ast.Yield) -> None:
        self.hasReturnValue = True

    def visit_YieldFrom(self, _node: ast.YieldFrom) -> None:
        self.hasReturnValue = True


def _format_snippet_choice(index: int, choiceList: list[str]) -> str:
    def escape_snippet_choice(value: str) -> str:
        return value.replace("\\", "\\\\").replace(",", "\\,").replace("|", "\\|")

    return f"${{{index}|{','.join(escape_snippet_choice(strChoice) for strChoice in choiceList)}|}}"


def _escape_snippet_placeholder_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("$", "\\$").replace("}", "\\}")


def _is_supported_literal(value: object) -> bool:
    if (
        value is None
        or value is Ellipsis
        or isinstance(value, bool | int | float | complex | str | bytes)
    ):
        return True

    if isinstance(value, list | tuple):
        return all(_is_supported_literal(item) for item in value)

    if isinstance(value, dict):
        return all(
            _is_supported_literal(key) and _is_supported_literal(item)
            for key, item in value.items()
        )

    return False


def _get_default_source(defaultObj: ast.expr) -> str:
    try:
        value = ast.literal_eval(defaultObj)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as e:
        raise ValueError(
            "The parameter default value is not a supported static literal."
        ) from e

    if not _is_supported_literal(value):
        raise ValueError("The parameter default value is not a supported static literal.")

    return repr(value)


def _get_annotation_name(annotationObj: ast.expr | None) -> str | None:
    if annotationObj is None:
        return None

    try:
        return ast.unparse(annotationObj)
    except Exception:
        return None


def _get_literal_choices(
    annotationObj: ast.expr | None, defaultSource: str | None
) -> list[str] | None:
    if not isinstance(annotationObj, ast.Subscript):
        return None

    valueObj = annotationObj.value
    boolIsLiteral = isinstance(valueObj, ast.Name) and valueObj.id == "Literal"
    boolIsTypingLiteral = (
        isinstance(valueObj, ast.Attribute) and valueObj.attr == "Literal"
    )

    if not boolIsLiteral and not boolIsTypingLiteral:
        return None

    listElement = (
        list(annotationObj.slice.elts)
        if isinstance(annotationObj.slice, ast.Tuple)
        else [annotationObj.slice]
    )
    listChoice: list[str] = []

    for elementObj in listElement:
        try:
            value = ast.literal_eval(elementObj)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            return None

        if not _is_supported_literal(value) or isinstance(value, list | dict | tuple):
            return None

        listChoice.append(repr(value))

    if defaultSource is not None and defaultSource in listChoice:
        listChoice = [
            defaultSource,
            *(choice for choice in listChoice if choice != defaultSource),
        ]

    return listChoice


def _get_bool_choices(
    annotationObj: ast.expr | None, defaultSource: str | None
) -> list[str] | None:
    boolHasBoolAnnotation = (
        isinstance(annotationObj, ast.Name) and annotationObj.id == "bool"
    )
    boolHasBoolDefault = defaultSource in {"True", "False"}

    if not boolHasBoolAnnotation and not boolHasBoolDefault:
        return None

    if defaultSource == "True":
        return ["True", "False"]

    if defaultSource == "False":
        return ["False", "True"]

    return None


def _format_parameter(
    parameterObj: ast.arg,
    index: int,
    defaultObj: ast.expr | None,
    *,
    positionalOnly: bool,
) -> str:
    strDefaultSource = _get_default_source(defaultObj) if defaultObj is not None else None

    listChoice = _get_literal_choices(parameterObj.annotation, strDefaultSource)

    if listChoice is None:
        listChoice = _get_bool_choices(parameterObj.annotation, strDefaultSource)

    if listChoice is not None:
        strPlaceholder = _format_snippet_choice(index=index, choiceList=listChoice)
    elif strDefaultSource is not None:
        strEscapedDefault = _escape_snippet_placeholder_text(strDefaultSource)
        strPlaceholder = f"${{{index}:{strEscapedDefault}}}"
    else:
        strPlaceholder = f"${{{index}:{parameterObj.arg}}}"

    if positionalOnly:
        return strPlaceholder

    return f"{parameterObj.arg}={strPlaceholder}"


def _function_has_return_value(functionObj: ast.FunctionDef) -> bool:
    strAnnotation = _get_annotation_name(functionObj.returns)

    if strAnnotation is not None:
        strNormalizedAnnotation = strAnnotation.replace(" ", "")
        if strNormalizedAnnotation in {"None", "NoneType", "type(None)"}:
            return False
        return True

    visitorObj = _FunctionReturnVisitor()
    for statementObj in functionObj.body:
        visitorObj.visit(statementObj)
        if visitorObj.hasReturnValue:
            return True

    return False


def _get_return_placeholder(functionObj: ast.FunctionDef) -> str:
    strAnnotation = _get_annotation_name(functionObj.returns)
    if strAnnotation is None:
        return "result"

    strLower = strAnnotation.replace(" ", "").lower()

    if strLower in {"str", "builtins.str"}:
        return "strResult"
    if strLower in {"int", "builtins.int"}:
        return "intResult"
    if strLower in {"float", "builtins.float"}:
        return "floatResult"
    if strLower in {"bool", "builtins.bool"}:
        return "boolResult"
    if strLower.startswith(("list[", "typing.list[")):
        return "listResult"
    if strLower.startswith(("dict[", "typing.dict[")):
        return "dictResult"
    if strLower.startswith(("tuple[", "typing.tuple[")):
        return "tupleResult"

    strSimpleName = strAnnotation.rsplit(".", 1)[-1]
    if strSimpleName.endswith("Obj") and strSimpleName.isidentifier():
        # Convert the first character into lowercase.
        if strSimpleName == "":
            return strSimpleName
        return strSimpleName[0].lower() + strSimpleName[1:]

    return "result"


def _build_function_body(moduleAlias: str, functionObj: ast.FunctionDef) -> list[str]:
    argumentsObj = functionObj.args

    if argumentsObj.vararg is not None or argumentsObj.kwarg is not None:
        raise ValueError("Functions with *args or **kwargs are not supported.")

    listPositionalParameter = [*argumentsObj.posonlyargs, *argumentsObj.args]
    intDefaultStart = len(listPositionalParameter) - len(argumentsObj.defaults)
    listCallParameter: list[str] = []
    intIndex = 1

    strReturnPart = ""
    if _function_has_return_value(functionObj):
        strPlaceholder = _get_return_placeholder(functionObj)
        strReturnPart = f"${{{intIndex}:{strPlaceholder}}} = "
        intIndex += 1

    for intParameterIndex, parameterObj in enumerate(listPositionalParameter):
        defaultObj = None
        if intParameterIndex >= intDefaultStart:
            defaultObj = argumentsObj.defaults[intParameterIndex - intDefaultStart]

        listCallParameter.append(
            _format_parameter(
                parameterObj,
                intIndex,
                defaultObj,
                positionalOnly=intParameterIndex < len(argumentsObj.posonlyargs),
            )
        )
        intIndex += 1

    for parameterObj, defaultObj in zip(
        argumentsObj.kwonlyargs, argumentsObj.kw_defaults, strict=True
    ):
        listCallParameter.append(
            _format_parameter(
                parameterObj,
                intIndex,
                defaultObj,
                positionalOnly=False,
            )
        )
        intIndex += 1

    strCall = f"{moduleAlias}.{functionObj.name}({', '.join(listCallParameter)})"
    return [f"{strReturnPart}{strCall}", "$0"]


def _build_diagnostic(
    code: str,
    modulePath: Path,
    projectPath: Path,
    line: int,
    message: str,
    functionName: str | None = None,
) -> DictComponentManagementWarning_SnippetDiagnostic:
    dictResult: DictComponentManagementWarning_SnippetDiagnostic = {
        "code": code,
        "file": modulePath.relative_to(projectPath).as_posix(),
        "line": line,
        "message": message,
    }

    if functionName is not None:
        dictResult["functionName"] = functionName

    return dictResult


def _is_overload_function(functionObj: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decoratorObj in functionObj.decorator_list:
        if isinstance(decoratorObj, ast.Name) and decoratorObj.id == "overload":
            return True

        if isinstance(decoratorObj, ast.Attribute) and decoratorObj.attr == "overload":
            return True

    return False


def _scan_module(
    modulePath: Path,
    projectPath: Path,
    packageName: str,
) -> tuple[
    dict[str, DictSnippet_Normalized],
    list[DictComponentManagementWarning_SnippetDiagnostic],
    list[DictComponentManagementWarning_SnippetDiagnostic],
]:
    try:
        with tokenize.open(modulePath) as fileObj:
            strSource = fileObj.read()
        moduleObj = ast.parse(
            strSource,
            filename=str(modulePath),
            type_comments=True,
        )
    except (OSError, SyntaxError, UnicodeError) as e:
        intLine = getattr(e, "lineno", 1) or 1
        raise ComponentManagementError(
            code="ast_snippet_scan_failed",
            message=f"Failed to parse Component Module: {modulePath.name}",
            details={
                "file": modulePath.relative_to(projectPath).as_posix(),
                "line": intLine,
                "reason": str(e),
            },
        ) from e

    strModuleName = modulePath.stem
    if not strModuleName.isidentifier():
        raise ComponentManagementError(
            code="component_source_invalid",
            message=f"Public Component Module filename is not a valid Python identifier: {modulePath.name}",
            details={"file": modulePath.relative_to(projectPath).as_posix()},
        )
    if keyword.iskeyword(strModuleName):
        raise ComponentManagementError(
            code="component_source_invalid",
            message=(
                f"Public Component Module filename cannot use a Python keyword: {modulePath.name}"
            ),
            details={"file": modulePath.relative_to(projectPath).as_posix()},
        )

    strModuleAlias = f"{packageName}_{strModuleName}"
    dictSnippet: dict[str, DictSnippet_Normalized] = {}
    listSkipped: list[DictComponentManagementWarning_SnippetDiagnostic] = []
    listWarning: list[DictComponentManagementWarning_SnippetDiagnostic] = []

    if _REGEX_COMPONENT_MODULE_NAME.fullmatch(strModuleName) is None:
        listWarning.append(
            _build_diagnostic(
                code="module_name_not_pascal_case",
                modulePath=modulePath,
                projectPath=projectPath,
                line=1,
                message=(
                    f"Public Component Module {strModuleName!r} does not use the recommended "
                    "PascalCase naming convention."
                ),
                functionName=None,
            )
        )

    dictFunctionDefinition: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for statementObj in moduleObj.body:
        if isinstance(
            statementObj, ast.FunctionDef | ast.AsyncFunctionDef
        ) and not statementObj.name.startswith("_"):
            dictFunctionDefinition.setdefault(statementObj.name, []).append(statementObj)

    listImplementation: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for strFunctionName, listDefinition in dictFunctionDefinition.items():
        listNonOverload = [
            functionObj
            for functionObj in listDefinition
            if not _is_overload_function(functionObj)
        ]

        if len(listNonOverload) == 0:
            listSkipped.append(
                _build_diagnostic(
                    code="missing_function_implementation",
                    modulePath=modulePath,
                    projectPath=projectPath,
                    line=listDefinition[0].lineno,
                    message="Only overload declarations were found; a concrete function implementation is required.",
                    functionName=strFunctionName,
                )
            )
            continue

        if len(listNonOverload) > 1:
            listSkipped.append(
                _build_diagnostic(
                    code="duplicate_function_definition",
                    modulePath=modulePath,
                    projectPath=projectPath,
                    line=listNonOverload[1].lineno,
                    message="More than one public implementation with the same function name was found.",
                    functionName=strFunctionName,
                )
            )
            continue

        listImplementation.append(listNonOverload[0])

    listImplementation.sort(key=lambda functionObj: functionObj.lineno)

    for functionObj in listImplementation:
        if isinstance(functionObj, ast.AsyncFunctionDef):
            listSkipped.append(
                _build_diagnostic(
                    code="unsupported_async_function",
                    modulePath=modulePath,
                    projectPath=projectPath,
                    line=functionObj.lineno,
                    functionName=functionObj.name,
                    message="Async functions are not converted into automatic Snippets.",
                )
            )
            continue

        try:
            listBody = _build_function_body(strModuleAlias, functionObj)
        except ValueError as e:
            listSkipped.append(
                _build_diagnostic(
                    code="unsupported_signature",
                    modulePath=modulePath,
                    projectPath=projectPath,
                    line=functionObj.lineno,
                    functionName=functionObj.name,
                    message=str(e),
                )
            )
            continue

        strDescription = ast.get_docstring(functionObj, clean=True)
        if strDescription is None or strDescription.strip() == "":
            strDescription = f"Call {strModuleAlias}.{functionObj.name}."
            listWarning.append(
                _build_diagnostic(
                    code="missing_docstring",
                    modulePath=modulePath,
                    projectPath=projectPath,
                    line=functionObj.lineno,
                    functionName=functionObj.name,
                    message="No non-empty function docstring was found. A fallback description was generated.",
                )
            )

        strSnippetKey = f"{strModuleAlias}.{functionObj.name}"
        dictSnippet[strSnippetKey] = {
            "category": strModuleAlias,
            "label": functionObj.name,
            "prefix": strSnippetKey,
            "body": listBody,
            "description": strDescription,
            "insertionMode": "line",
            "imports": {packageName: [strModuleName]},
        }

    return dictSnippet, listSkipped, listWarning


def scan_component_snippets(
    projectPath: Path,
    packagePath: Path,
    manifestObj: Info_ProjectManifest_Component,
) -> DictSnippet_AstFile:
    dictSnippet: dict[str, DictSnippet_Normalized] = {}
    listSkipped: list[DictComponentManagementWarning_SnippetDiagnostic] = []
    listWarning: list[DictComponentManagementWarning_SnippetDiagnostic] = []

    listModulePath = sorted(
        (
            path
            for path in packagePath.iterdir()
            if path.is_file()
            and path.suffix.casefold() == ".py"
            and path.name != "__init__.py"
            and not path.name.startswith("_")
        ),
        key=lambda path: path.name,
    )

    for pathModule in listModulePath:
        dictModuleSnippet, listModuleSkipped, listModuleWarning = _scan_module(
            modulePath=pathModule,
            projectPath=projectPath,
            packageName=manifestObj.packageName,
        )
        dictSnippet.update(dictModuleSnippet)
        listSkipped.extend(listModuleSkipped)
        listWarning.extend(listModuleWarning)

    listSkipped.sort(
        key=lambda item: (item["file"], item["line"], item.get("functionName", ""))
    )
    listWarning.sort(
        key=lambda item: (item["file"], item["line"], item.get("functionName", ""))
    )

    return {
        "schemaVersion": 1,
        "componentId": manifestObj.id,
        "packageName": manifestObj.packageName,
        "snippets": dictSnippet,
        "skipped": listSkipped,
        "warnings": listWarning,
    }
