# FileName: _PublishComponent.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import write_json_atomic
from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Common._Validation import path_exists, is_file_invalid, is_folder_invalid
from liberrpa.ComponentManagement.Types._Warning import (
    DictComponentManagementWarning_Operation,
    DictComponentManagementWarning,
)
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Snippet import DictSnippet_AstFile
from liberrpa.ComponentManagement.Types._Publish import (
    Info_Publish_PreparationCreated,
    Info_Publish_Published,
    Info_PublishResult,
)
from liberrpa.ComponentManagement.Domain.Lock._ProjectLock import project_lock
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import read_component_manifest
from liberrpa.ComponentManagement.Application.Repository._PublishComponentWheel import publish_component_wheel
from liberrpa.ComponentManagement.Domain.Snippet._Ast import scan_component_snippets
from liberrpa.ComponentManagement.Domain.Snippet._Config import create_snippet_config, build_snippet_catalog
from liberrpa.ComponentManagement.Domain.Wheel._Wheel import build_component_wheel

from pathlib import Path
from shutil import rmtree
import uuid


def _validate_component_project(
    projectPath: Path,
) -> tuple[Info_ProjectManifest_Component, Path]:
    pathComponentManifest = projectPath / "component.json"
    pathFlowManifest = projectPath / "flow.json"

    if path_exists(pathFlowManifest):
        raise ComponentManagementError(
            code="not_component_project",
            message="Publish Component is only available for a Component Project.",
            details={"flowManifest": str(pathFlowManifest)},
        )

    manifestObj = read_component_manifest(pathComponentManifest)
    pathSrc = projectPath / "src"
    pathPackage = pathSrc / manifestObj.packageName

    if is_folder_invalid(pathSrc):
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

    if is_folder_invalid(pathPackage):
        raise ComponentManagementError(
            code="component_source_invalid",
            message=f"Component package folder was not found or is invalid: {pathPackage}",
        )

    for strRequiredFile in ("__init__.py", "py.typed"):
        pathRequiredFile = pathPackage / strRequiredFile
        if is_file_invalid(pathRequiredFile):
            raise ComponentManagementError(
                code="component_source_invalid",
                message=f"Required Component package file was not found or is invalid: {pathRequiredFile}",
            )

    return manifestObj, pathPackage


def _write_ast_snippets(astSnippetsPath: Path, astSnippetsDict: DictSnippet_AstFile) -> None:
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
        if path_exists(pathBuildRoot):
            if is_folder_invalid(pathBuildRoot):
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
) -> DictComponentManagementWarning_Operation | None:
    try:
        if path_exists(buildRootPath):
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
) -> Info_PublishResult:
    pathProject = resolve_project_path(projectInputPath)

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
            return Info_Publish_PreparationCreated(
                status="preparationCreated",
                projectPath=pathProject,
                componentId=manifestObj.id,
                packageName=manifestObj.packageName,
                astSnippetsPath=pathAstSnippetsFile,
                snippetsConfigPath=pathSnippetsJsoncFile,
                generatedCount=len(dictAstSnippets["snippets"]),
                skippedCount=len(dictAstSnippets["skipped"]),
                warnings=listWarning,
            )

        dictBuildResult = build_snippet_catalog(
            configPath=pathSnippetsJsoncFile,
            astSnippets=dictAstSnippets,
            packagePath=pathPackage,
            manifestObj=manifestObj,
        )
        listWarning.extend(item for item in dictBuildResult.warnings)

        pathBuildRoot, pathBuildFolder = _prepare_build_folder(pathProject)

        dictCleanupWarning: DictComponentManagementWarning_Operation | None = None

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

        return Info_Publish_Published(
            status=repositoryResult.status,
            projectPath=pathProject,
            componentId=manifestObj.id,
            packageName=manifestObj.packageName,
            version=manifestObj.version,
            wheelFile=wheelResult.wheelFile,
            sha256=wheelResult.sha256,
            astSnippetsPath=pathAstSnippetsFile,
            snippetsConfigPath=pathSnippetsJsoncFile,
            generatedCount=len(dictAstSnippets["snippets"]),
            skippedCount=len(dictAstSnippets["skipped"]),
            excludedCount=dictBuildResult.excludedCount,
            handWrittenCount=dictBuildResult.handWrittenCount,
            finalCount=len(dictBuildResult.catalog["snippets"]),
            warnings=listWarning,
        )
