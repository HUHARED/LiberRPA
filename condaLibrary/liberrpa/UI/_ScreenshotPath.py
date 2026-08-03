# FileName: _ScreenshotPath.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._Exception import UiSelectorError
from liberrpa.Common._TypedValue import StrPath
from liberrpa.Common._Utils import PATH_PROJECT_ROOT
from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Validation import path_exists
from liberrpa.ComponentManagement.Types._Manifest import (
    Str_ProjectType,
    Info_ProjectManifest_Component,
    Info_ProjectManifest,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    is_components_lock_stale,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import read_project_manifest

from pathlib import Path, PureWindowsPath
import os
import shutil


PATH_SCREENSHOT_DOCUMENTS = Path(os.environ.get("USERPROFILE", "N/A")) / R"Documents\LiberRPA\Screenshots"
PATH_SCREENSHOT_DOCUMENTS.mkdir(parents=True, exist_ok=True)
_PATH_FULL_SCREENSHOT = PATH_SCREENSHOT_DOCUMENTS / "LiberRPA_full_screenshot.png"

STR_FULL_SCREENSHOT = str(_PATH_FULL_SCREENSHOT)
STR_SCREENSHOT_TEMP_NAME = "captured_temp.png"


def _get_screenshot_file_name(fileName: StrPath) -> str:
    strFileName = os.fspath(fileName)
    pathFileName = PureWindowsPath(strFileName)

    if strFileName in {"", ".", ".."} or pathFileName.is_absolute() or pathFileName.name != strFileName:
        raise UiSelectorError(
            "SelectorImage FileName must contain only a file name, not an absolute path or folder path: "
            f"{strFileName!r}."
        )

    return strFileName


def _read_project_manifest_for_screenshot(
    projectPath: Path,
) -> tuple[Str_ProjectType, Info_ProjectManifest] | None:
    try:
        return read_project_manifest(projectPath)
    except ComponentManagementError as e:
        if e.code == "project_manifest_missing":
            return None

        raise UiSelectorError(
            f"Failed to resolve SelectorImage screenshot paths because the Project manifest is invalid: {e.message}"
        ) from e


def _get_locked_component_screenshot_file_candidates(
    projectPath: Path,
    manifestObj: Info_ProjectManifest,
    fileName: str,
) -> list[Path]:
    if not manifestObj.componentDependencies:
        return []

    pathLock = projectPath / STR_COMPONENTS_LOCK_FILE_NAME
    try:
        dictLock = read_components_lock(pathLock)
    except ComponentManagementError as e:
        raise UiSelectorError(
            f"A valid components.lock.json is required to resolve Component SelectorImage resources: {e.message}"
        ) from e

    if is_components_lock_stale(dictLock, manifestObj):
        raise UiSelectorError(
            "components.lock.json is stale. Reapply the Project Component dependencies before using Component SelectorImage resources."
        )

    return [
        projectPath / "_Components" / dictComponent["packageName"] / "_Screenshots" / fileName
        for dictComponent in dictLock["components"].values()
    ]


def get_managed_screenshot_file_candidates(
    fileName: StrPath,
    projectPath: Path = PATH_PROJECT_ROOT,
) -> list[Path]:
    strFileName = _get_screenshot_file_name(fileName)
    tupleProjectManifest = _read_project_manifest_for_screenshot(projectPath)
    if tupleProjectManifest is None:
        return []

    strProjectType, manifestObj = tupleProjectManifest
    if strProjectType == "component":
        assert isinstance(manifestObj, Info_ProjectManifest_Component)
        listCandidate = [projectPath / "src" / manifestObj.packageName / "_Screenshots" / strFileName]
    else:
        listCandidate = [projectPath / "_Screenshots" / strFileName]

    listCandidate.extend(
        _get_locked_component_screenshot_file_candidates(
            projectPath=projectPath,
            manifestObj=manifestObj,
            fileName=strFileName,
        )
    )

    return [pathCandidate for pathCandidate in listCandidate if pathCandidate.is_file()]


def _get_project_screenshot_folder(projectPath: Path = PATH_PROJECT_ROOT) -> Path:
    tupleProjectManifest = _read_project_manifest_for_screenshot(projectPath)
    if tupleProjectManifest is None:
        raise UiSelectorError(
            f"Cannot determine the Project screenshot folder because no flow.json or component.json exists in {projectPath}."
        )

    strProjectType, manifestObj = tupleProjectManifest
    if strProjectType == "flow":
        return projectPath / "_Screenshots"

    assert isinstance(manifestObj, Info_ProjectManifest_Component)
    return projectPath / "src" / manifestObj.packageName / "_Screenshots"


def move_documents_screenshot_to_project(
    fileName: StrPath,
    projectPath: Path = PATH_PROJECT_ROOT,
) -> Path:
    strFileName = _get_screenshot_file_name(fileName)
    pathSource = PATH_SCREENSHOT_DOCUMENTS / strFileName
    if not pathSource.is_file():
        raise FileNotFoundError(f"Screenshot file was not found in Documents: {pathSource}")

    pathTargetFolder = _get_project_screenshot_folder(projectPath)
    pathTarget = pathTargetFolder / strFileName
    if path_exists(pathTarget):
        raise FileExistsError(f"The target screenshot path already exists: {pathTarget}")

    pathTargetFolder.mkdir(parents=True, exist_ok=True)
    pathMoved = Path(shutil.move(pathSource, pathTarget))
    return pathMoved.resolve()
