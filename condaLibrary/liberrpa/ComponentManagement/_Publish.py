# FileName: _Publish.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement._Exception import ComponentManagementError
from liberrpa.ComponentManagement._File import write_json_atomic
from liberrpa.ComponentManagement._Manifest import ComponentManifest, read_component_manifest
from liberrpa.ComponentManagement._ProjectLock import project_lock
from liberrpa.ComponentManagement._SnippetAst import DictAstSnippetsFile, scan_component_snippets
from liberrpa.ComponentManagement._SnippetConfig import build_snippet_catalog, create_snippet_config
from liberrpa.ComponentManagement._Wheel import build_component_wheel

from pathlib import Path


def _validate_component_project(
    projectPath: Path,
) -> tuple[ComponentManifest, Path]:
    pathComponentManifest = projectPath / "component.json"
    pathFlowManifest = projectPath / "flow.json"

    if pathFlowManifest.exists():
        raise ComponentManagementError(
            code="not_component_project",
            message="Publish Component is only available for a Component Project.",
            details={"flowManifest": str(pathFlowManifest)},
        )

    manifestObj = read_component_manifest(pathComponentManifest)
    pathSrc = projectPath / "src"
    pathPackage = pathSrc / manifestObj.packageName

    if not pathSrc.is_dir():
        raise ComponentManagementError(
            code="component_source_invalid",
            message=f"Component source folder was not found: {pathSrc}",
        )

    listUnexpectedEntry = sorted(entry.name for entry in pathSrc.iterdir() if entry.name != manifestObj.packageName)
    if listUnexpectedEntry:
        raise ComponentManagementError(
            code="component_source_invalid",
            message="The src folder can only contain the Component's top-level package.",
            details={"unexpectedEntries": listUnexpectedEntry},
        )

    if not pathPackage.is_dir() or pathPackage.is_symlink():
        raise ComponentManagementError(
            code="component_source_invalid",
            message=f"Component package folder was not found or is invalid: {pathPackage}",
        )

    for strRequiredFile in ("__init__.py", "py.typed"):
        pathRequiredFile = pathPackage / strRequiredFile
        if not pathRequiredFile.is_file() or pathRequiredFile.is_symlink():
            raise ComponentManagementError(
                code="component_source_invalid",
                message=f"Required Component package file was not found or is invalid: {pathRequiredFile}",
            )

    return manifestObj, pathPackage


def _write_ast_snippets(astSnippetsPath: Path, astSnippets: DictAstSnippetsFile) -> None:
    try:
        write_json_atomic(path=astSnippetsPath, value=astSnippets)
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to write AST Snippet scan result: {astSnippetsPath}",
        ) from e


def publish_component(projectInputPath: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    pathProject = Path(projectInputPath).expanduser().resolve()

    if not pathProject.is_dir():
        raise ComponentManagementError(
            code="project_path_invalid",
            message=f"Project folder was not found: {pathProject}",
        )

    with project_lock(projectPath=pathProject, operation="publishComponent"):
        manifestObj, pathPackage = _validate_component_project(pathProject)
        dictAstSnippets = scan_component_snippets(
            projectPath=pathProject,
            packagePath=pathPackage,
            manifestObj=manifestObj,
        )

        pathSnippetsFolder = pathProject / "_Snippets"
        pathAstSnippets = pathSnippetsFolder / "ast.snippets.json"
        pathSnippetConfig = pathSnippetsFolder / "snippets.jsonc"

        _write_ast_snippets(astSnippetsPath=pathAstSnippets, astSnippets=dictAstSnippets)
        boolConfigCreated = create_snippet_config(configPath=pathSnippetConfig)

        listWarning: list[dict[str, object]] = [dict(item) for item in dictAstSnippets["warnings"]]
        if boolConfigCreated:
            dictResult: dict[str, object] = {
                "status": "preparationCreated",
                "componentId": manifestObj.id,
                "packageName": manifestObj.packageName,
                "astSnippetsFile": pathAstSnippets.relative_to(pathProject).as_posix(),
                "snippetsConfigFile": pathSnippetConfig.relative_to(pathProject).as_posix(),
                "generatedCount": len(dictAstSnippets["snippets"]),
                "skippedCount": len(dictAstSnippets["skipped"]),
                "warningCount": len(listWarning),
            }
            return dictResult, listWarning

        dicBuildResult = build_snippet_catalog(
            configPath=pathSnippetConfig,
            astSnippets=dictAstSnippets,
            packagePath=pathPackage,
            manifestObj=manifestObj,
        )
        listWarning.extend(dict(item) for item in dicBuildResult.warnings)

        wheelResult = build_component_wheel(
            projectPath=pathProject,
            packagePath=pathPackage,
            manifestObj=manifestObj,
            snippetCatalog=dicBuildResult.catalog,
        )

        dictResult = {
            "status": "wheelBuilt",
            "componentId": manifestObj.id,
            "packageName": manifestObj.packageName,
            "version": manifestObj.version,
            "wheelFile": wheelResult.wheelFile,
            "wheelPath": wheelResult.wheelPath.relative_to(pathProject).as_posix(),
            "sha256": wheelResult.sha256,
            "astSnippetsFile": pathAstSnippets.relative_to(pathProject).as_posix(),
            "snippetsConfigFile": pathSnippetConfig.relative_to(pathProject).as_posix(),
            "generatedCount": len(dictAstSnippets["snippets"]),
            "skippedCount": len(dictAstSnippets["skipped"]),
            "excludedCount": dicBuildResult.excludedCount,
            "handWrittenCount": dicBuildResult.handWrittenCount,
            "finalCount": len(dicBuildResult.catalog["snippets"]),
            "warningCount": len(listWarning),
        }
        return dictResult, listWarning
