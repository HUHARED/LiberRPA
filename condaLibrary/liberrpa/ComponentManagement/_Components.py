# FileName: _Components.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import parse_json
from liberrpa.ComponentManagement.Utils._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Utils._TypedValue import (
    ComponentManifest,
    ComponentWheelInfo,
    DictLockedComponent,
    DictComponentsLockFile,
    ComponentsFolderInfo,
)
from liberrpa.ComponentManagement.Utils._WheelName import get_component_wheel_names
from liberrpa.ComponentManagement.Utils._Record import validate_archive_path, validate_record
from liberrpa.ComponentManagement._ComponentsLock import validate_components_lock
from liberrpa.ComponentManagement._Manifest import parse_component_manifest
from liberrpa.ComponentManagement._RepositoryIndex import get_wheel_path
from liberrpa.ComponentManagement._Wheel import inspect_component_wheel

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
    wheelPath: Path
    archivePathTuple: tuple[str, ...]


def _validate_lock_dict(lockDict: DictComponentsLockFile) -> DictComponentsLockFile:
    try:
        dictValidatedLock = validate_components_lock(lockDict)
    except ValueError as e:
        raise ComponentManagementError(
            code="components_lock_invalid",
            message="Cannot use an invalid components.lock.json.",
            details={"reason": str(e)},
        ) from e

    if not dictValidatedLock["components"]:
        raise ComponentManagementError(
            code="components_not_required",
            message="_Components is not required when the resolved Component set is empty.",
        )

    return dictValidatedLock


def _get_manifest_mismatch_dict(
    componentId: str,
    lockedComponent: DictLockedComponent,
    manifestObj: ComponentManifest,
) -> dict[str, object]:
    dictMismatch: dict[str, object] = {}

    dictExpectedValue: dict[str, object] = {
        "id": componentId,
        "schemaVersion": lockedComponent["manifestSchemaVersion"],
        "packageName": lockedComponent["packageName"],
        "displayName": lockedComponent["displayName"],
        "version": lockedComponent["version"],
        "requiresLiberrpa": lockedComponent["requiresLiberrpa"],
        "componentDependencies": lockedComponent["componentDependencies"],
    }
    dictActualValue: dict[str, object] = {
        "id": manifestObj.id,
        "schemaVersion": manifestObj.schemaVersion,
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
    lockedComponent: DictLockedComponent,
    wheelInfo: ComponentWheelInfo,
) -> None:
    if wheelInfo.wheelFile != lockedComponent["wheelFile"]:
        raise ComponentManagementError(
            code="component_wheel_lock_mismatch",
            message="A Component Wheel filename does not match components.lock.json.",
            details={
                "componentId": componentId,
                "expectedWheelFile": lockedComponent["wheelFile"],
                "actualWheelFile": wheelInfo.wheelFile,
            },
        )

    if wheelInfo.sha256 != lockedComponent["sha256"]:
        raise ComponentManagementError(
            code="component_wheel_hash_mismatch",
            message="A Component Wheel does not match the SHA-256 in components.lock.json.",
            details={
                "componentId": componentId,
                "wheelFile": wheelInfo.wheelFile,
                "expectedSha256": lockedComponent["sha256"],
                "actualSha256": wheelInfo.sha256,
            },
        )

    dictMismatch = _get_manifest_mismatch_dict(
        componentId,
        lockedComponent,
        wheelInfo.manifest,
    )
    if dictMismatch:
        raise ComponentManagementError(
            code="component_wheel_lock_mismatch",
            message="A Component Wheel Manifest does not match components.lock.json.",
            details={
                "componentId": componentId,
                "wheelFile": wheelInfo.wheelFile,
                "mismatches": dictMismatch,
            },
        )


def _register_archive_path(
    archivePath: str,
    *,
    componentId: str,
    pathRegistry: dict[str, tuple[str, str, str]],
) -> None:
    listPathPart = archivePath.split("/")

    for intIndex in range(1, len(listPathPart)):
        strDirectoryPath = "/".join(listPathPart[:intIndex])
        strDirectoryKey = strDirectoryPath.casefold()
        existingEntry = pathRegistry.get(strDirectoryKey)

        if existingEntry is None:
            pathRegistry[strDirectoryKey] = (strDirectoryPath, "directory", componentId)
            continue

        strExistingPath, strExistingType, strExistingOwner = existingEntry
        if strExistingPath != strDirectoryPath or strExistingType != "directory" or strExistingOwner != componentId:
            raise ComponentManagementError(
                code="components_path_conflict",
                message="Component Wheels contain paths that conflict when expanded into _Components.",
                details={
                    "paths": [strExistingPath, strDirectoryPath],
                    "componentIds": [strExistingOwner, componentId],
                },
            )

    strFileKey = archivePath.casefold()
    existingEntry = pathRegistry.get(strFileKey)
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

    pathRegistry[strFileKey] = (archivePath, "file", componentId)


def _prepare_locked_wheel_source_list(
    repositoryPath: Path,
    lockDict: DictComponentsLockFile,
) -> list[_LockedWheelSource]:
    listLockedWheelSource: list[_LockedWheelSource] = []
    dictPathRegistry: dict[str, tuple[str, str, str]] = {}

    for strComponentId, dictLockedComponent in lockDict["components"].items():
        pathWheel = get_wheel_path(
            repositoryPath=repositoryPath,
            componentId=strComponentId,
            packageName=dictLockedComponent["packageName"],
            wheelFile=dictLockedComponent["wheelFile"],
        )

        if not pathWheel.is_file() or pathWheel.is_symlink():
            raise ComponentManagementError(
                code="component_wheel_missing",
                message="A Component Wheel required by components.lock.json was not found.",
                details={
                    "componentId": strComponentId,
                    "wheelFile": str(pathWheel),
                },
            )

        wheelInfo = inspect_component_wheel(pathWheel)
        _validate_locked_wheel(
            strComponentId,
            dictLockedComponent,
            wheelInfo,
        )

        try:
            with ZipFile(pathWheel, mode="r") as wheelObj:
                tupleArchivePath = tuple(infoObj.filename for infoObj in wheelObj.infolist())

            for strArchivePath in tupleArchivePath:
                validate_archive_path(strArchivePath)
                _register_archive_path(
                    strArchivePath,
                    componentId=strComponentId,
                    pathRegistry=dictPathRegistry,
                )
        except ComponentManagementError:
            raise
        except (BadZipFile, OSError, ValueError) as e:
            raise ComponentManagementError(
                code="component_wheel_changed",
                message="A Component Wheel changed after it was validated.",
                details={
                    "componentId": strComponentId,
                    "wheelFile": str(pathWheel),
                },
            ) from e

        listLockedWheelSource.append(
            _LockedWheelSource(
                componentId=strComponentId,
                wheelPath=pathWheel,
                archivePathTuple=tupleArchivePath,
            )
        )

    return listLockedWheelSource


def _extract_locked_wheel(
    lockedWheelSource: _LockedWheelSource,
    targetPath: Path,
    expectedSha256: str,
) -> None:
    try:
        with ZipFile(lockedWheelSource.wheelPath, mode="r") as wheelObj:
            tupleCurrentArchivePath = tuple(infoObj.filename for infoObj in wheelObj.infolist())
            if tupleCurrentArchivePath != lockedWheelSource.archivePathTuple:
                raise ComponentManagementError(
                    code="component_wheel_changed",
                    message="A Component Wheel changed while _Components was being built.",
                    details={
                        "componentId": lockedWheelSource.componentId,
                        "wheelFile": str(lockedWheelSource.wheelPath),
                    },
                )

            for strArchivePath in lockedWheelSource.archivePathTuple:
                pathArchiveTarget = targetPath.joinpath(*PurePosixPath(strArchivePath).parts)
                pathArchiveTarget.parent.mkdir(parents=True, exist_ok=True)

                with wheelObj.open(strArchivePath, mode="r") as sourceFileObj:
                    with pathArchiveTarget.open("xb") as targetFileObj:
                        copyfileobj(sourceFileObj, targetFileObj)
    except ComponentManagementError:
        raise
    except (BadZipFile, KeyError, OSError) as e:
        raise ComponentManagementError(
            code="components_build_failed",
            message="Failed to expand a Component Wheel into _Components.",
            details={
                "componentId": lockedWheelSource.componentId,
                "wheelFile": str(lockedWheelSource.wheelPath),
            },
        ) from e

    try:
        strCurrentSha256 = calculate_file_sha256(lockedWheelSource.wheelPath)
    except OSError as e:
        raise ComponentManagementError(
            code="repository_unavailable",
            message=f"Failed to read Component Wheel: {lockedWheelSource.wheelPath}",
        ) from e

    if strCurrentSha256 != expectedSha256:
        raise ComponentManagementError(
            code="component_wheel_changed",
            message="A Component Wheel changed while _Components was being built.",
            details={
                "componentId": lockedWheelSource.componentId,
                "wheelFile": str(lockedWheelSource.wheelPath),
                "expectedSha256": expectedSha256,
                "actualSha256": strCurrentSha256,
            },
        )


def _scan_components_folder(componentsPath: Path) -> tuple[set[str], set[str]]:
    setFilePath: set[str] = set()
    setDirectoryPath: set[str] = set()
    dictCaseInsensitivePath: dict[str, tuple[str, str]] = {}
    listPendingFolder: list[tuple[Path, tuple[str, ...]]] = [(componentsPath, ())]

    while listPendingFolder:
        pathFolder, tupleRelativePart = listPendingFolder.pop()

        try:
            listEntry = sorted(os.scandir(pathFolder), key=lambda entryObj: entryObj.name)
        except OSError as e:
            raise ValueError(f"Failed to read _Components folder {pathFolder}: {e}.") from e

        for entryObj in listEntry:
            tupleEntryPart = (*tupleRelativePart, entryObj.name)
            strRelativePath = PurePosixPath(*tupleEntryPart).as_posix()

            if entryObj.is_symlink():
                raise ValueError(f"_Components cannot contain symbolic links: {strRelativePath!r}.")

            if entryObj.is_dir(follow_symlinks=False):
                if entryObj.name == "__pycache__":
                    continue

                strPathType = "directory"
                setDirectoryPath.add(strRelativePath)
                listPendingFolder.append((Path(entryObj.path), tupleEntryPart))
            elif entryObj.is_file(follow_symlinks=False):
                if Path(entryObj.name).suffix.casefold() in _SET_IGNORED_FILE_SUFFIX:
                    continue

                strPathType = "file"
                setFilePath.add(strRelativePath)
            else:
                raise ValueError(f"_Components contains an unsupported path: {strRelativePath!r}.")

            strPathKey = strRelativePath.casefold()
            existingEntry = dictCaseInsensitivePath.get(strPathKey)
            if existingEntry is not None:
                strExistingPath, strExistingType = existingEntry
                raise ValueError(
                    "_Components contains paths that conflict on Windows: "
                    f"{strExistingPath!r} ({strExistingType}), {strRelativePath!r} ({strPathType})."
                )

            dictCaseInsensitivePath[strPathKey] = (strRelativePath, strPathType)

    return setFilePath, setDirectoryPath


def _read_components_file(componentsPath: Path, archivePath: str) -> bytes:
    pathFile = componentsPath.joinpath(*PurePosixPath(archivePath).parts)

    try:
        return pathFile.read_bytes()
    except OSError as e:
        raise ValueError(f"Failed to read _Components file {archivePath!r}: {e}.") from e


def _validate_extracted_component(
    componentsPath: Path,
    componentId: str,
    lockedComponent: DictLockedComponent,
    actualFilePathSet: set[str],
) -> set[str]:
    strPackageName = lockedComponent["packageName"]
    strDistInfoFolder, _ = get_component_wheel_names(
        strPackageName,
        lockedComponent["version"],
    )
    strRecordPath = f"{strDistInfoFolder}/RECORD"
    strManifestPath = f"{strDistInfoFolder}/component.json"

    setComponentFilePath = {
        strPath
        for strPath in actualFilePathSet
        if PurePosixPath(strPath).parts[0] in {strPackageName, strDistInfoFolder}
    }
    setExpectedDistInfoPath = {
        f"{strDistInfoFolder}/METADATA",
        f"{strDistInfoFolder}/WHEEL",
        f"{strDistInfoFolder}/licenses/LICENSE",
        strManifestPath,
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
        raise ValueError(f"Component {componentId} is missing required files: {listMissingPath}.")

    setActualDistInfoPath = {
        strPath for strPath in setComponentFilePath if PurePosixPath(strPath).parts[0] == strDistInfoFolder
    }
    if setActualDistInfoPath != setExpectedDistInfoPath:
        raise ValueError(
            f"Component {componentId} .dist-info files do not match the expected structure. "
            f"Unexpected: {sorted(setActualDistInfoPath - setExpectedDistInfoPath)}."
        )

    try:
        embeddedManifest = parse_json(
            _read_components_file(componentsPath, strManifestPath).decode("utf-8", errors="strict")
        )
        manifestObj = parse_component_manifest(
            embeddedManifest,
            sourceName=strManifestPath,
        )
    except ComponentManagementError as e:
        raise ValueError(f"Component {componentId} contains an invalid embedded component.json: {e.message}.") from e
    except (UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"Component {componentId} contains an invalid embedded component.json: {e}.") from e

    dictMismatch = _get_manifest_mismatch_dict(
        componentId,
        lockedComponent,
        manifestObj,
    )
    if dictMismatch:
        raise ValueError(
            f"Component {componentId} embedded component.json does not match components.lock.json: {dictMismatch}."
        )

    validate_record(
        archivePathSet=setComponentFilePath,
        recordPath=strRecordPath,
        readArchiveFile=lambda archivePath: _read_components_file(componentsPath, archivePath),
    )

    return setComponentFilePath


def validate_components_folder(
    componentsPath: Path,
    lockDict: DictComponentsLockFile,
) -> ComponentsFolderInfo:
    """Validate _Components against embedded Manifests and Wheel RECORD files."""
    dictValidatedLock = _validate_lock_dict(lockDict)

    if not componentsPath.exists():
        raise ComponentManagementError(
            code="components_folder_missing",
            message=f"_Components folder was not found: {componentsPath}",
        )

    if not componentsPath.is_dir() or componentsPath.is_symlink():
        raise ComponentManagementError(
            code="components_folder_damaged",
            message=f"_Components path is invalid: {componentsPath}",
        )

    try:
        setActualFilePath, setActualDirectoryPath = _scan_components_folder(componentsPath)
        setOwnedFilePath: set[str] = set()

        for strComponentId, dictLockedComponent in dictValidatedLock["components"].items():
            setComponentFilePath = _validate_extracted_component(
                componentsPath,
                strComponentId,
                dictLockedComponent,
                setActualFilePath,
            )
            setOverlappingPath = setOwnedFilePath & setComponentFilePath
            if setOverlappingPath:
                raise ValueError(f"Multiple Components claim the same extracted files: {sorted(setOverlappingPath)}.")
            setOwnedFilePath.update(setComponentFilePath)

        listUnknownFilePath = sorted(setActualFilePath - setOwnedFilePath)
        if listUnknownFilePath:
            raise ValueError(f"_Components contains unknown files: {listUnknownFilePath}.")

        setExpectedDirectoryPath: set[str] = set()
        for strFilePath in setOwnedFilePath:
            listPathPart = strFilePath.split("/")
            setExpectedDirectoryPath.update(
                "/".join(listPathPart[:intIndex]) for intIndex in range(1, len(listPathPart))
            )

        listMissingDirectoryPath = sorted(setExpectedDirectoryPath - setActualDirectoryPath)
        listUnknownDirectoryPath = sorted(setActualDirectoryPath - setExpectedDirectoryPath)
        if listMissingDirectoryPath or listUnknownDirectoryPath:
            raise ValueError(
                "_Components directory structure does not match the locked Wheels. "
                f"Missing: {listMissingDirectoryPath}; unknown: {listUnknownDirectoryPath}."
            )
    except ComponentManagementError:
        raise
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="components_folder_damaged",
            message=f"_Components integrity validation failed: {componentsPath}",
            details={"reason": str(e)},
        ) from e

    return ComponentsFolderInfo(
        componentsPath=componentsPath,
        componentCount=len(dictValidatedLock["components"]),
        fileCount=len(setActualFilePath),
    )


def build_components_folder(
    repositoryPath: Path,
    targetPath: Path,
    lockDict: DictComponentsLockFile,
) -> ComponentsFolderInfo:
    """Build a complete _Components folder from exact immutable Repository Wheels."""
    dictValidatedLock = _validate_lock_dict(lockDict)

    if not repositoryPath.is_dir():
        raise ComponentManagementError(
            code="repository_unavailable",
            message=f"Component Repository folder was not found: {repositoryPath}",
        )

    if targetPath.exists() or targetPath.is_symlink():
        raise ComponentManagementError(
            code="components_target_exists",
            message=f"_Components build target already exists: {targetPath}",
        )

    listLockedWheelSource = _prepare_locked_wheel_source_list(
        repositoryPath,
        dictValidatedLock,
    )
    pathTemp = targetPath.parent / f".{targetPath.name}.{uuid.uuid4()}.tmp"

    try:
        targetPath.parent.mkdir(parents=True, exist_ok=True)
        pathTemp.mkdir()

        for lockedWheelSource in listLockedWheelSource:
            _extract_locked_wheel(
                lockedWheelSource,
                pathTemp,
                dictValidatedLock["components"][lockedWheelSource.componentId]["sha256"],
            )

        folderInfo = validate_components_folder(pathTemp, dictValidatedLock)

        if targetPath.exists() or targetPath.is_symlink():
            raise ComponentManagementError(
                code="components_target_exists",
                message=f"_Components build target appeared while it was being built: {targetPath}",
            )

        os.replace(pathTemp, targetPath)
    except ComponentManagementError:
        raise
    except OSError as e:
        raise ComponentManagementError(
            code="components_build_failed",
            message=f"Failed to build _Components: {targetPath}",
        ) from e
    finally:
        if pathTemp.exists() and not pathTemp.is_symlink():
            rmtree(pathTemp, ignore_errors=True)

    return ComponentsFolderInfo(
        componentsPath=targetPath,
        componentCount=folderInfo.componentCount,
        fileCount=folderInfo.fileCount,
    )
