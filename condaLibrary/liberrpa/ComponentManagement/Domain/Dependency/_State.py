# FileName: _State.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Common._Version import get_installed_liberrpa_version
from liberrpa.ComponentManagement.Common._Validation import path_exists, is_file_invalid
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest
from liberrpa.ComponentManagement.Types._Components import DictComponentsLock_File
from liberrpa.ComponentManagement.Types._Dependency import (
    Str_ProjectDependency_LockState,
    Str_ProjectDependency_ComponentsState,
    Str_ProjectDependency_EnvironmentState,
    Str_ProjectDependency_RepairState,
    Info_ProjectDependency_State,
)
from liberrpa.ComponentManagement.Domain.Project._Components import (
    STR_COMPONENTS_FOLDER_NAME,
    validate_components_folder,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    STR_COMPONENTS_LOCK_FILE_NAME,
    read_components_lock,
    is_components_lock_stale,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import read_project_manifest
from liberrpa.ComponentManagement.Domain.Repository._RepositoryPath import get_repository_path
from liberrpa.ComponentManagement.Domain.Repository._Index import get_wheel_path

from pathlib import Path
from packaging.specifiers import SpecifierSet


def _get_environment_state(
    manifestObj: Info_ProjectManifest,
    lockDict: DictComponentsLock_File | None,
    lockState: Str_ProjectDependency_LockState,
) -> tuple[Str_ProjectDependency_EnvironmentState, dict[str, object]]:
    if manifestObj.componentDependencies and lockState != "valid":
        return "unknown", {
            "reason": "A valid components.lock.json is required before all LiberRPA version requirements can be checked."
        }

    try:
        installedVersionObj = get_installed_liberrpa_version()
    except ValueError as e:
        return "unknown", {"reason": str(e)}

    strInstalledVersion = str(installedVersionObj)

    listRequirement: list[tuple[str, str]] = [("Project", manifestObj.requiresLiberrpa)]
    if lockDict is not None:
        listRequirement.extend(
            (f"Component {componentId}", component["requiresLiberrpa"])
            for componentId, component in lockDict["components"].items()
        )

    listIncompatibleRequirement = [
        {
            "source": strSource,
            "requiresLiberrpa": strSpecifier,
        }
        for strSource, strSpecifier in listRequirement
        if not SpecifierSet(strSpecifier).contains(installedVersionObj)
    ]

    if listIncompatibleRequirement:
        return "incompatible", {
            "installedLiberrpaVersion": strInstalledVersion,
            "incompatibleRequirements": listIncompatibleRequirement,
        }

    return "compatible", {"installedLiberrpaVersion": strInstalledVersion}


def _get_components_state(
    projectPath: Path,
    *,
    dependenciesRequired: bool,
    lockState: Str_ProjectDependency_LockState,
    lockDict: DictComponentsLock_File | None,
) -> tuple[Str_ProjectDependency_ComponentsState, dict[str, object]]:
    if not dependenciesRequired:
        return "notRequired", {}

    if lockState != "valid" or lockDict is None:
        return "unverified", {"reason": "A valid components.lock.json is required before _Components can be verified."}

    pathComponents = projectPath / STR_COMPONENTS_FOLDER_NAME
    if not pathComponents.exists() and not pathComponents.is_symlink():
        return "missing", {"componentsPath": str(pathComponents)}

    if pathComponents.is_dir() and not pathComponents.is_symlink():
        try:
            if not any(pathComponents.iterdir()):
                return "missing", {"componentsPath": str(pathComponents)}
        except OSError as e:
            return "damaged", {
                "componentsPath": str(pathComponents),
                "reason": str(e),
            }

    try:
        folderInfo = validate_components_folder(pathComponents, lockDict)
    except ComponentManagementError as e:
        return "damaged", {
            "componentsPath": str(pathComponents),
            "code": e.code,
            "message": e.message,
            "details": e.details or {},
        }

    return "valid", {
        "componentsPath": str(pathComponents),
        "componentCount": folderInfo.componentCount,
        "fileCount": folderInfo.fileCount,
    }


def _get_repair_state(
    lockDict: DictComponentsLock_File | None,
    lockState: Str_ProjectDependency_LockState,
    componentsState: Str_ProjectDependency_ComponentsState,
) -> tuple[Str_ProjectDependency_RepairState, dict[str, object]]:
    if lockState != "valid" or lockDict is None or componentsState in {"notRequired", "valid"}:
        return "notApplicable", {}

    try:
        pathRepository = get_repository_path()
    except ComponentManagementError as e:
        return "repositoryUnavailable", {
            "code": e.code,
            "message": e.message,
            "details": e.details or {},
        }

    for strComponentId, dictComponent in lockDict["components"].items():
        pathWheel = get_wheel_path(
            repositoryPath=pathRepository,
            componentId=strComponentId,
            packageName=dictComponent["packageName"],
            wheelFile=dictComponent["wheelFile"],
        )

        if is_file_invalid(pathWheel):
            return "wheelMissing", {
                "componentId": strComponentId,
                "wheelFile": str(pathWheel),
            }

        try:
            strActualSha256 = calculate_file_sha256(pathWheel)
        except OSError as e:
            return "repositoryUnavailable", {
                "wheelFile": str(pathWheel),
                "reason": str(e),
            }

        if strActualSha256 != dictComponent["sha256"]:
            return "wheelHashMismatch", {
                "componentId": strComponentId,
                "wheelFile": str(pathWheel),
                "expectedSha256": dictComponent["sha256"],
                "actualSha256": strActualSha256,
            }

    return "available", {"repositoryPath": str(pathRepository)}


def get_project_dependency_state(projectPath: Path) -> Info_ProjectDependency_State:
    pathProject = resolve_project_path(projectPath)

    strProjectType, manifestObj = read_project_manifest(pathProject)
    boolDependenciesRequired = bool(manifestObj.componentDependencies)
    pathLock = pathProject / STR_COMPONENTS_LOCK_FILE_NAME
    dictDetails: dict[str, object] = {}

    lockState: Str_ProjectDependency_LockState
    dictComponentsLock: DictComponentsLock_File | None = None

    if not boolDependenciesRequired:
        lockState = "notRequired"
        if path_exists(pathLock):
            dictDetails["unusedLockFile"] = str(pathLock)
    elif not pathLock.exists() and not pathLock.is_symlink():
        lockState = "missing"
        dictDetails["lockFile"] = str(pathLock)
    else:
        try:
            dictComponentsLock = read_components_lock(pathLock)
        except ComponentManagementError as e:
            lockState = "invalid"
            dictDetails["lockError"] = {
                "code": e.code,
                "message": e.message,
                "details": e.details or {},
            }
        else:
            if is_components_lock_stale(dictComponentsLock, manifestObj):
                lockState = "stale"
                dictDetails["actualLockRoot"] = dictComponentsLock["root"]
            else:
                lockState = "valid"

    componentsState, dictComponentsDetails = _get_components_state(
        pathProject,
        dependenciesRequired=boolDependenciesRequired,
        lockState=lockState,
        lockDict=dictComponentsLock,
    )
    if dictComponentsDetails:
        dictDetails["components"] = dictComponentsDetails

    environmentState, dictEnvironmentDetails = _get_environment_state(
        manifestObj,
        dictComponentsLock,
        lockState,
    )
    if dictEnvironmentDetails:
        dictDetails["environment"] = dictEnvironmentDetails

    repairState, dictRepairDetails = _get_repair_state(
        dictComponentsLock,
        lockState,
        componentsState,
    )
    if dictRepairDetails:
        dictDetails["repair"] = dictRepairDetails

    return Info_ProjectDependency_State(
        projectPath=pathProject,
        projectType=strProjectType,
        manifest=manifestObj,
        componentsLock=dictComponentsLock,
        lockState=lockState,
        componentsState=componentsState,
        environmentState=environmentState,
        repairState=repairState,
        details=dictDetails,
    )
