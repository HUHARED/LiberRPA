# FileName: _Publish.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import write_json_atomic
from liberrpa.ComponentManagement.Utils._TypedValue import (
    DictOperationWarning,
    DictComponentManagementWarning,
    ComponentManifest,
    DictAstSnippetsFile,
    DictPreparationCreatedResult,
    DictPublishedComponentResult,
    DictPublishComponentResult,
)
from liberrpa.ComponentManagement._Manifest import read_component_manifest
from liberrpa.ComponentManagement.Lock._ProjectLock import project_lock
from liberrpa.ComponentManagement._Repository import publish_component_wheel
from liberrpa.ComponentManagement._SnippetAst import scan_component_snippets
from liberrpa.ComponentManagement._SnippetConfig import build_snippet_catalog, create_snippet_config
from liberrpa.ComponentManagement._Wheel import build_component_wheel

from pathlib import Path
from shutil import rmtree
import uuid


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


def _write_ast_snippets(astSnippetsPath: Path, astSnippetsDict: DictAstSnippetsFile) -> None:
    try:
        write_json_atomic(path=astSnippetsPath, value=astSnippetsDict)
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to write AST Snippet scan result: {astSnippetsPath}",
        ) from e


def _prepare_build_folder(projectPath: Path) -> tuple[Path, Path]:
    pathBuildRoot = projectPath / ".liberrpa-project-manager" / "build"

    try:
        if pathBuildRoot.exists():
            if pathBuildRoot.is_symlink() or not pathBuildRoot.is_dir():
                raise ComponentManagementError(
                    code="component_build_path_invalid",
                    message=f"Component build path is invalid: {pathBuildRoot}",
                )

            rmtree(pathBuildRoot)

        pathBuildFolder = pathBuildRoot / f"publish_{uuid.uuid4()}"
        pathBuildFolder.mkdir(parents=True)
    except ComponentManagementError:
        raise
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to prepare Component build folder: {pathBuildRoot}",
        ) from e

    return pathBuildRoot, pathBuildFolder


def _cleanup_build_output(
    buildRootPath: Path,
) -> DictOperationWarning | None:
    try:
        if buildRootPath.exists():
            rmtree(buildRootPath)

        pathManager = buildRootPath.parent
        if pathManager.is_dir() and not any(pathManager.iterdir()):
            pathManager.rmdir()
    except OSError as e:
        return {
            "code": "build_cleanup_pending",
            "message": (
                f"The Component operation completed, but temporary build files could not be removed: {buildRootPath}"
            ),
            "details": {"reason": str(e)},
        }

    return None


def publish_component(
    projectInputPath: str,
) -> tuple[
    DictPublishComponentResult,
    list[DictComponentManagementWarning],
]:
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
        pathAstSnippetsFile = pathSnippetsFolder / "ast.snippets.json"
        pathSnippetsJsoncFile = pathSnippetsFolder / "snippets.jsonc"

        _write_ast_snippets(astSnippetsPath=pathAstSnippetsFile, astSnippetsDict=dictAstSnippets)
        boolConfigCreated = create_snippet_config(configPath=pathSnippetsJsoncFile)

        listWarning: list[DictComponentManagementWarning] = list(dictAstSnippets["warnings"])
        if boolConfigCreated:
            dictPreparationResult: DictPreparationCreatedResult = {
                "status": "preparationCreated",
                "componentId": manifestObj.id,
                "packageName": manifestObj.packageName,
                "astSnippetsFile": pathAstSnippetsFile.relative_to(pathProject).as_posix(),
                "snippetsJsoncFile": pathSnippetsJsoncFile.relative_to(pathProject).as_posix(),
                "generatedCount": len(dictAstSnippets["snippets"]),
                "skippedCount": len(dictAstSnippets["skipped"]),
                "warningCount": len(listWarning),
            }
            return dictPreparationResult, listWarning

        dictBuildResult = build_snippet_catalog(
            configPath=pathSnippetsJsoncFile,
            astSnippets=dictAstSnippets,
            packagePath=pathPackage,
            manifestObj=manifestObj,
        )
        listWarning.extend(item for item in dictBuildResult.warnings)

        pathBuildRoot, pathBuildFolder = _prepare_build_folder(pathProject)

        dictCleanupWarning: DictOperationWarning | None = None

        try:
            wheelResult = build_component_wheel(
                projectPath=pathProject,
                packagePath=pathPackage,
                buildFolderPath=pathBuildFolder,
                manifestObj=manifestObj,
                snippetCatalog=dictBuildResult.catalog,
            )

            repositoryResult = publish_component_wheel(
                manifestObj=manifestObj,
                wheelResult=wheelResult,
            )
        finally:
            dictCleanupWarning = _cleanup_build_output(pathBuildRoot)

        # Reaching here means the Wheel build and Repository publish both succeeded.
        if dictCleanupWarning is not None:
            listWarning.append(dictCleanupWarning)

        listWarning.extend(repositoryResult.warnings)

        dictPublishedResult: DictPublishedComponentResult = {
            "status": repositoryResult.status,
            "componentId": manifestObj.id,
            "packageName": manifestObj.packageName,
            "version": manifestObj.version,
            "wheelFile": wheelResult.wheelFile,
            "sha256": wheelResult.sha256,
            "astSnippetsFile": pathAstSnippetsFile.relative_to(pathProject).as_posix(),
            "snippetsJsoncFile": pathSnippetsJsoncFile.relative_to(pathProject).as_posix(),
            "generatedCount": len(dictAstSnippets["snippets"]),
            "skippedCount": len(dictAstSnippets["skipped"]),
            "excludedCount": dictBuildResult.excludedCount,
            "handWrittenCount": dictBuildResult.handWrittenCount,
            "finalCount": len(dictBuildResult.catalog["snippets"]),
            "warningCount": len(listWarning),
        }
        return dictPublishedResult, listWarning
