# FileName: _Components.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import parse_json
from liberrpa.ComponentManagement.Common._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Common._WheelName import get_component_wheel_names
from liberrpa.ComponentManagement.Common._Record import (
    validate_archive_path,
    validate_record,
)
from liberrpa.ComponentManagement.Common._Validation import (
    path_exists,
    is_file_invalid,
    is_folder_invalid,
)
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Wheel import Info_ComponentWheel
from liberrpa.ComponentManagement.Types._Components import (
    DictComponentsLock_Component,
    DictComponentsLock_File,
    Info_ProjectComponentsFolder,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import (
    parse_component_manifest,
)
from liberrpa.ComponentManagement.Domain.Repository._Index import get_wheel_file_path
from liberrpa.ComponentManagement.Domain.Wheel._Wheel import inspect_component_wheel

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from shutil import copyfileobj, rmtree
from zipfile import BadZipFile, ZipFile
import os
import uuid


"""
All locked Component Wheels are flattened into one Project folder:

_Components/
├── PackageA/
├── PackageB/
├── distribution_a-version.dist-info/
└── distribution_b-version.dist-info/

The folder is rebuilt from exact Repository Wheels and treated as read-only Project state.
"""


STR_COMPONENTS_FOLDER_NAME = "_Components"

_SET_IGNORED_FILE_SUFFIX = {".pyc"}


@dataclass(frozen=True)
class _LockedWheelSource:
    componentId: str
    wheelFilePath: Path
    archivePathTuple: tuple[str, ...]


def _get_manifest_mismatch_dict(
    componentId: str,
    lockedComponentDict: DictComponentsLock_Component,
    manifestObj: Info_ProjectManifest_Component,
) -> dict[str, object]:
    dictMismatch: dict[str, object] = {}

    dictExpectedValue: dict[str, object] = {
        "id": componentId,
        "packageName": lockedComponentDict["packageName"],
        "displayName": lockedComponentDict["displayName"],
        "version": lockedComponentDict["version"],
        "requiresLiberrpa": lockedComponentDict["requiresLiberrpa"],
        "componentDependencies": lockedComponentDict["componentDependencies"],
    }
    dictActualValue: dict[str, object] = {
        "id": manifestObj.id,
        "packageName": manifestObj.packageName,
        "displayName": manifestObj.displayName,
        "version": manifestObj.version,
        "requiresLiberrpa": manifestObj.requiresLiberrpa,
        "componentDependencies": manifestObj.componentDependencies,
    }

    for strField, expectedValue in dictExpectedValue.items():
        actualValue = dictActualValue[strField]
        if actualValue != expectedValue:
            dictMismatch[strField] = {
                "expected": expectedValue,
                "actual": actualValue,
            }

    return dictMismatch


def _validate_locked_wheel(
    componentId: str,
    lockedComponent: DictComponentsLock_Component,
    wheelInfoObj: Info_ComponentWheel,
) -> None:
    if wheelInfoObj.wheelFileName != lockedComponent["wheelFileName"]:
        raise ComponentManagementError(
            code="component_wheel_lock_mismatch",
            message="A Component Wheel filename does not match components.lock.json.",
            details={
                "componentId": componentId,
                "expectedWheelFileName": lockedComponent["wheelFileName"],
                "actualWheelFileName": wheelInfoObj.wheelFileName,
            },
        )

    if wheelInfoObj.sha256 != lockedComponent["sha256"]:
        raise ComponentManagementError(
            code="component_wheel_hash_mismatch",
            message="A Component Wheel does not match the SHA-256 in components.lock.json.",
            details={
                "componentId": componentId,
                "wheelFileName": wheelInfoObj.wheelFileName,
                "expectedSha256": lockedComponent["sha256"],
                "actualSha256": wheelInfoObj.sha256,
            },
        )

    dictMismatch = _get_manifest_mismatch_dict(
        componentId,
        lockedComponent,
        wheelInfoObj.manifest,
    )
    if dictMismatch:
        raise ComponentManagementError(
            code="component_wheel_lock_mismatch",
            message="A Component Wheel Manifest does not match components.lock.json.",
            details={
                "componentId": componentId,
                "wheelFileName": wheelInfoObj.wheelFileName,
                "mismatches": dictMismatch,
            },
        )


def _register_archive_path(
    archivePath: str,
    *,
    componentId: str,
    archivePathRegistry: dict[str, tuple[str, str, str]],
) -> None:
    """
    Register one Wheel archive file and its parent folders before extraction.

    The registry prevents case-insensitive path collisions, file/folder conflicts, duplicate files, and multiple Components from claiming the same extracted folder when all locked Wheels are flattened into _Components.
    """

    listPathPart = archivePath.split("/")

    for intIndex in range(1, len(listPathPart)):
        strFolderPath = "/".join(listPathPart[:intIndex])
        strFolderKey = strFolderPath.casefold()
        existingEntry = archivePathRegistry.get(strFolderKey)

        if existingEntry is None:
            archivePathRegistry[strFolderKey] = (strFolderPath, "folder", componentId)
            continue

        strExistingPath, strExistingType, strExistingOwner = existingEntry
        if (
            strExistingPath != strFolderPath
            or strExistingType != "folder"
            or strExistingOwner != componentId
        ):
            raise ComponentManagementError(
                code="components_path_conflict",
                message="Component Wheels contain paths that conflict when expanded into _Components.",
                details={
                    "paths": [strExistingPath, strFolderPath],
                    "componentIds": [strExistingOwner, componentId],
                },
            )

    strFileKey = archivePath.casefold()
    existingEntry = archivePathRegistry.get(strFileKey)
    if existingEntry is not None:
        strExistingPath, _, strExistingOwner = existingEntry
        raise ComponentManagementError(
            code="components_path_conflict",
            message="Component Wheels contain paths that conflict when expanded into _Components.",
            details={
                "paths": [strExistingPath, archivePath],
                "componentIds": [strExistingOwner, componentId],
            },
        )

    archivePathRegistry[strFileKey] = (archivePath, "file", componentId)


def _prepare_locked_wheel_source_list(
    repositoryPath: Path,
    lockDict: DictComponentsLock_File,
) -> list[_LockedWheelSource]:
    listLockedWheelSource: list[_LockedWheelSource] = []
    dictArchivePathRegistry: dict[str, tuple[str, str, str]] = {}

    for strComponentId, dictLockedComponent in lockDict["components"].items():
        pathWheelFile = get_wheel_file_path(
            repositoryPath=repositoryPath,
            componentId=strComponentId,
            packageName=dictLockedComponent["packageName"],
            wheelFileName=dictLockedComponent["wheelFileName"],
        )

        if is_file_invalid(pathWheelFile):
            raise ComponentManagementError(
                code="component_wheel_missing",
                message="A Component Wheel required by components.lock.json was not found.",
                details={
                    "componentId": strComponentId,
                    "wheelFilePath": str(pathWheelFile),
                },
            )

        wheelInfoObj = inspect_component_wheel(pathWheelFile)
        _validate_locked_wheel(
            strComponentId,
            dictLockedComponent,
            wheelInfoObj,
        )

        try:
            with ZipFile(pathWheelFile, mode="r") as wheelObj:
                tupleArchivePath = tuple(
                    infoObj.filename for infoObj in wheelObj.infolist()
                )

            for strArchivePath in tupleArchivePath:
                validate_archive_path(archivePath=strArchivePath)
                _register_archive_path(
                    strArchivePath,
                    componentId=strComponentId,
                    archivePathRegistry=dictArchivePathRegistry,
                )
        except ComponentManagementError:
            raise
        except (BadZipFile, OSError, ValueError) as e:
            raise ComponentManagementError(
                code="component_wheel_changed",
                message="A Component Wheel changed after it was validated.",
                details={
                    "componentId": strComponentId,
                    "wheelFilePath": str(pathWheelFile),
                },
            ) from e

        listLockedWheelSource.append(
            _LockedWheelSource(
                componentId=strComponentId,
                wheelFilePath=pathWheelFile,
                archivePathTuple=tupleArchivePath,
            )
        )

    return listLockedWheelSource


def _extract_locked_wheel(
    lockedWheelSource: _LockedWheelSource,
    targetComponentsFolderPath: Path,
    expectedSha256: str,
) -> None:
    try:
        with ZipFile(lockedWheelSource.wheelFilePath, mode="r") as wheelObj:
            tupleCurrentArchivePath = tuple(
                infoObj.filename for infoObj in wheelObj.infolist()
            )
            if tupleCurrentArchivePath != lockedWheelSource.archivePathTuple:
                raise ComponentManagementError(
                    code="component_wheel_changed",
                    message="A Component Wheel changed while _Components was being built.",
                    details={
                        "componentId": lockedWheelSource.componentId,
                        "wheelFilePath": str(lockedWheelSource.wheelFilePath),
                    },
                )

            for strArchivePath in lockedWheelSource.archivePathTuple:
                pathExtractedFile = targetComponentsFolderPath.joinpath(
                    *PurePosixPath(strArchivePath).parts
                )
                pathExtractedFile.parent.mkdir(parents=True, exist_ok=True)

                with wheelObj.open(strArchivePath, mode="r") as sourceFileObj:
                    with pathExtractedFile.open("xb") as targetFileObj:
                        copyfileobj(sourceFileObj, targetFileObj)
    except ComponentManagementError:
        raise
    except (BadZipFile, KeyError, OSError) as e:
        raise ComponentManagementError(
            code="components_build_failed",
            message="Failed to expand a Component Wheel into _Components.",
            details={
                "componentId": lockedWheelSource.componentId,
                "wheelFilePath": str(lockedWheelSource.wheelFilePath),
            },
        ) from e

    try:
        strCurrentSha256 = calculate_file_sha256(lockedWheelSource.wheelFilePath)
    except OSError as e:
        raise ComponentManagementError(
            code="repository_unavailable",
            message=f"Failed to read Component Wheel: {lockedWheelSource.wheelFilePath}",
        ) from e

    if strCurrentSha256 != expectedSha256:
        raise ComponentManagementError(
            code="component_wheel_changed",
            message="A Component Wheel changed while _Components was being built.",
            details={
                "componentId": lockedWheelSource.componentId,
                "wheelFilePath": str(lockedWheelSource.wheelFilePath),
                "expectedSha256": expectedSha256,
                "actualSha256": strCurrentSha256,
            },
        )


def _scan_components_folder(componentsFolderPath: Path) -> tuple[set[str], set[str]]:
    """
    Scan _Components and collect its actual file and folder paths.

    Traverse the folder recursively and return the relative paths of all managed files and folders using POSIX-style separators so they can be compared with Wheel archive and RECORD paths.

    Ignore Python runtime artifacts such as __pycache__ folders and .pyc files.
    Reject symbolic links, unsupported file-system entries, and case-insensitive path collisions because _Components must remain deterministic and safe to validate on Windows.

    Returns:
        A tuple containing the sets of managed file paths and managed folder paths relative to _Components.
    """

    setFilePath: set[str] = set()
    setFolderPath: set[str] = set()
    dictCaseInsensitivePath: dict[str, tuple[str, str]] = {}
    listPendingFolder: list[tuple[Path, tuple[str, ...]]] = [(componentsFolderPath, ())]

    while listPendingFolder:
        pathFolder, tupleRelativePart = listPendingFolder.pop()

        try:
            listEntry = sorted(os.scandir(pathFolder), key=lambda entryObj: entryObj.name)
        except OSError as e:
            raise ValueError(
                f"Failed to read _Components folder {pathFolder}: {e}."
            ) from e

        for entryObj in listEntry:
            tupleEntryPart = (*tupleRelativePart, entryObj.name)
            strRelativePath = PurePosixPath(*tupleEntryPart).as_posix()

            if entryObj.is_symlink():
                raise ValueError(
                    f"_Components cannot contain symbolic links: {strRelativePath!r}."
                )

            if entryObj.is_dir(follow_symlinks=False):
                if entryObj.name == "__pycache__":
                    continue

                strPathType = "folder"
                setFolderPath.add(strRelativePath)
                listPendingFolder.append((Path(entryObj.path), tupleEntryPart))
            elif entryObj.is_file(follow_symlinks=False):
                if Path(entryObj.name).suffix.casefold() in _SET_IGNORED_FILE_SUFFIX:
                    continue

                strPathType = "file"
                setFilePath.add(strRelativePath)
            else:
                raise ValueError(
                    f"_Components contains an unsupported path: {strRelativePath!r}."
                )

            strPathKey = strRelativePath.casefold()
            existingEntry = dictCaseInsensitivePath.get(strPathKey)
            if existingEntry is not None:
                strExistingPath, strExistingType = existingEntry
                raise ValueError(
                    "_Components contains paths that conflict on Windows: "
                    f"{strExistingPath!r} ({strExistingType}), {strRelativePath!r} ({strPathType})."
                )

            dictCaseInsensitivePath[strPathKey] = (strRelativePath, strPathType)

    return setFilePath, setFolderPath


def _read_components_file(componentsFolderPath: Path, archivePath: str) -> bytes:
    pathComponentsFile = componentsFolderPath.joinpath(*PurePosixPath(archivePath).parts)

    try:
        return pathComponentsFile.read_bytes()
    except OSError as e:
        raise ValueError(f"Failed to read _Components file {archivePath!r}: {e}.") from e


def _validate_extracted_component(
    componentsFolderPath: Path,
    componentId: str,
    lockedComponentDict: DictComponentsLock_Component,
    actualFilePathSet: set[str],
) -> set[str]:
    strPackageName = lockedComponentDict["packageName"]
    strDistInfoFolder, _ = get_component_wheel_names(
        strPackageName,
        lockedComponentDict["version"],
    )
    strRecordPath = f"{strDistInfoFolder}/RECORD"
    strManifestFilePath = f"{strDistInfoFolder}/component.json"

    setComponentFilePath = {
        strPath
        for strPath in actualFilePathSet
        if PurePosixPath(strPath).parts[0] in {strPackageName, strDistInfoFolder}
    }
    setExpectedDistInfoPath = {
        f"{strDistInfoFolder}/METADATA",
        f"{strDistInfoFolder}/WHEEL",
        f"{strDistInfoFolder}/licenses/LICENSE",
        strManifestFilePath,
        f"{strDistInfoFolder}/snippets_catalog.json",
        strRecordPath,
    }
    setRequiredPath = {
        f"{strPackageName}/__init__.py",
        f"{strPackageName}/py.typed",
        *setExpectedDistInfoPath,
    }
    listMissingPath = sorted(setRequiredPath - setComponentFilePath)
    if listMissingPath:
        raise ValueError(
            f"Component {componentId} is missing required files: {listMissingPath}."
        )

    setActualDistInfoPath = {
        strPath
        for strPath in setComponentFilePath
        if PurePosixPath(strPath).parts[0] == strDistInfoFolder
    }
    if setActualDistInfoPath != setExpectedDistInfoPath:
        raise ValueError(
            f"Component {componentId} .dist-info files do not match the expected structure. "
            f"Unexpected: {sorted(setActualDistInfoPath - setExpectedDistInfoPath)}."
        )

    try:
        embeddedManifest = parse_json(
            _read_components_file(componentsFolderPath, strManifestFilePath).decode(
                "utf-8", errors="strict"
            )
        )
        manifestObj = parse_component_manifest(
            embeddedManifest,
            sourceName=strManifestFilePath,
        )
    except ComponentManagementError as e:
        raise ValueError(
            f"Component {componentId} contains an invalid embedded component.json: {e.message}."
        ) from e
    except (UnicodeDecodeError, ValueError) as e:
        raise ValueError(
            f"Component {componentId} contains an invalid embedded component.json: {e}."
        ) from e

    dictMismatch = _get_manifest_mismatch_dict(
        componentId,
        lockedComponentDict,
        manifestObj,
    )
    if dictMismatch:
        raise ValueError(
            f"Component {componentId} embedded component.json does not match components.lock.json: {dictMismatch}."
        )

    validate_record(
        archivePathSet=setComponentFilePath,
        recordPath=strRecordPath,
        readArchiveFile=lambda archivePath: _read_components_file(
            componentsFolderPath, archivePath
        ),
    )

    return setComponentFilePath


def _ensure_components_required(
    lockDict: DictComponentsLock_File,
) -> None:
    if not lockDict["components"]:
        raise ComponentManagementError(
            code="components_not_required",
            message=(
                "_Components is not required when the resolved Component set is empty."
            ),
        )


def validate_components_folder(
    componentsFolderPath: Path,
    lockDict: DictComponentsLock_File,
) -> Info_ProjectComponentsFolder:
    """Validate _Components against embedded Manifests and Wheel RECORD files."""
    _ensure_components_required(lockDict)

    if not path_exists(componentsFolderPath):
        raise ComponentManagementError(
            code="components_folder_missing",
            message=f"_Components folder was not found: {componentsFolderPath}",
        )

    if is_folder_invalid(componentsFolderPath):
        raise ComponentManagementError(
            code="components_folder_damaged",
            message=f"_Components path is invalid: {componentsFolderPath}",
        )

    try:
        setActualFilePath, setActualFolderPath = _scan_components_folder(
            componentsFolderPath
        )
        setOwnedFilePath: set[str] = set()

        for strComponentId, dictLockedComponent in lockDict["components"].items():
            setComponentFilePath = _validate_extracted_component(
                componentsFolderPath,
                strComponentId,
                dictLockedComponent,
                setActualFilePath,
            )
            setOverlappingPath = setOwnedFilePath & setComponentFilePath
            if setOverlappingPath:
                raise ValueError(
                    f"Multiple Components claim the same extracted files: {sorted(setOverlappingPath)}."
                )
            setOwnedFilePath.update(setComponentFilePath)

        listUnknownFilePath = sorted(setActualFilePath - setOwnedFilePath)
        if listUnknownFilePath:
            raise ValueError(
                f"_Components contains unknown files: {listUnknownFilePath}."
            )

        setExpectedFolderPath: set[str] = set()
        for strFilePath in setOwnedFilePath:
            listPathPart = strFilePath.split("/")
            setExpectedFolderPath.update(
                "/".join(listPathPart[:intIndex])
                for intIndex in range(1, len(listPathPart))
            )

        listMissingFolderPath = sorted(setExpectedFolderPath - setActualFolderPath)
        listUnknownFolderPath = sorted(setActualFolderPath - setExpectedFolderPath)
        if listMissingFolderPath or listUnknownFolderPath:
            raise ValueError(
                "_Components folder structure does not match the locked Wheels. "
                f"Missing: {listMissingFolderPath}; unknown: {listUnknownFolderPath}."
            )
    except ComponentManagementError:
        raise
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="components_folder_damaged",
            message=f"_Components integrity validation failed: {componentsFolderPath}",
            details={"reason": str(e)},
        ) from e

    return Info_ProjectComponentsFolder(
        componentsFolderPath=componentsFolderPath,
        componentCount=len(lockDict["components"]),
        fileCount=len(setActualFilePath),
    )


def build_components_folder(
    repositoryPath: Path,
    targetComponentsFolderPath: Path,
    lockDict: DictComponentsLock_File,
) -> Info_ProjectComponentsFolder:
    """Build a complete _Components folder from exact immutable Repository Wheels."""
    _ensure_components_required(lockDict)

    if is_folder_invalid(repositoryPath):
        raise ComponentManagementError(
            code="repository_unavailable",
            message=(
                f"Component Repository folder was not found or is invalid: {repositoryPath}"
            ),
        )

    if path_exists(targetComponentsFolderPath):
        raise ComponentManagementError(
            code="components_target_exists",
            message=f"_Components build target already exists: {targetComponentsFolderPath}",
        )

    listLockedWheelSource = _prepare_locked_wheel_source_list(
        repositoryPath,
        lockDict,
    )
    pathTempComponentsFolder = (
        targetComponentsFolderPath.parent
        / f".{targetComponentsFolderPath.name}.{uuid.uuid4()}.tmp"
    )

    try:
        targetComponentsFolderPath.parent.mkdir(parents=True, exist_ok=True)
        pathTempComponentsFolder.mkdir()

        for lockedWheelSource in listLockedWheelSource:
            _extract_locked_wheel(
                lockedWheelSource,
                pathTempComponentsFolder,
                lockDict["components"][lockedWheelSource.componentId]["sha256"],
            )

        folderInfo = validate_components_folder(pathTempComponentsFolder, lockDict)

        if path_exists(targetComponentsFolderPath):
            raise ComponentManagementError(
                code="components_target_exists",
                message=f"_Components build target appeared while it was being built: {targetComponentsFolderPath}",
            )

        os.replace(pathTempComponentsFolder, targetComponentsFolderPath)
    except ComponentManagementError:
        raise
    except OSError as e:
        raise ComponentManagementError(
            code="components_build_failed",
            message=f"Failed to build _Components: {targetComponentsFolderPath}",
        ) from e
    finally:
        if (
            pathTempComponentsFolder.exists()
            and not pathTempComponentsFolder.is_symlink()
        ):
            rmtree(pathTempComponentsFolder, ignore_errors=True)

    return Info_ProjectComponentsFolder(
        componentsFolderPath=targetComponentsFolderPath,
        componentCount=folderInfo.componentCount,
        fileCount=folderInfo.fileCount,
    )
