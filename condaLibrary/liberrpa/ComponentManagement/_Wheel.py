# FileName: _Wheel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import parse_json, serialize_json
from liberrpa.ComponentManagement.Utils._Hash import calculate_file_sha256, calculate_record_hash
from liberrpa.ComponentManagement.Utils._TypedValue import ComponentManifest, DictSnippetCatalogFile, WheelBuildResult

from csv import reader, writer
from email import policy
from email.message import Message
from email.parser import BytesParser
from io import StringIO
from pathlib import Path, PurePosixPath
from packaging.tags import Tag
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version
from zipfile import (
    ZIP_STORED,  # Use ZIP_STORED to keep the same content has the same zip binary results' size.
    BadZipFile,
    ZipFile,
    ZipInfo,
)
import os
import re
import stat
import uuid


_STR_WHEEL_TAG = "py313-none-any"  # Without any binary file related to system platforms or CPU architectures.
_TUPLE_ZIP_TIMESTAMP = (1984, 4, 4, 0, 0, 0)  # A fixed timestamp for keeping zip binary result same.
_INT_ZIP_FILE_MODE = (stat.S_IFREG | 0o644) << 16  # Owner can edit, others can read.

_SET_IGNORED_FILE_SUFFIX = {
    ".pyc",
    ".pyo",
}

_SET_FORBIDDEN_FILE_SUFFIX = {
    ".bat",
    ".cmd",
    ".dll",
    ".dylib",
    ".exe",
    ".ps1",
    ".pyd",
    ".so",
}

_REGEX_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")


def _get_wheel_names(manifestObj: ComponentManifest) -> tuple[str, str]:
    strDistributionName = canonicalize_name(manifestObj.packageName).replace("-", "_")
    strDistInfoFolder = f"{strDistributionName}-{manifestObj.version}.dist-info"
    strWheelFile = f"{strDistributionName}-{manifestObj.version}-{_STR_WHEEL_TAG}.whl"
    return strDistInfoFolder, strWheelFile


def _get_manifest_dict(manifestObj: ComponentManifest) -> dict[str, object]:
    return {
        "schemaVersion": manifestObj.schemaVersion,
        "id": manifestObj.id,
        "packageName": manifestObj.packageName,
        "displayName": manifestObj.displayName,
        "version": manifestObj.version,
        "description": manifestObj.description,
        "requiresLiberrpa": manifestObj.requiresLiberrpa,
        "componentDependencies": dict(sorted(manifestObj.componentDependencies.items())),
    }


def _get_package_archive_entries(
    packagePath: Path,
    packageName: str,
) -> dict[str, bytes]:
    """Determine which files can be packaged."""
    dictEntry: dict[str, bytes] = {}
    dictCaseInsensitivePath: dict[str, str] = {}

    for pathSource in sorted(packagePath.rglob("*"), key=lambda pathObj: pathObj.as_posix()):
        relativePath = pathSource.relative_to(packagePath)

        if "__pycache__" in relativePath.parts:
            continue

        if pathSource.is_symlink():
            raise ComponentManagementError(
                code="unsupported_component_file",
                message=f"Component package cannot contain symbolic links: {pathSource}",
                details={"file": relativePath.as_posix()},
            )

        if pathSource.is_dir():
            continue

        if not pathSource.is_file():
            raise ComponentManagementError(
                code="unsupported_component_file",
                message=f"Unsupported Component package entry: {pathSource}",
                details={"file": relativePath.as_posix()},
            )

        strSuffix = pathSource.suffix.casefold()

        if strSuffix in _SET_IGNORED_FILE_SUFFIX:
            continue

        if strSuffix in _SET_FORBIDDEN_FILE_SUFFIX:
            raise ComponentManagementError(
                code="unsupported_component_file",
                message=f"Unsupported Component package file type: {pathSource}",
                details={"file": relativePath.as_posix()},
            )

        strArchivePath = PurePosixPath(packageName, *relativePath.parts).as_posix()
        strCaseInsensitivePath = strArchivePath.casefold()
        strExistingPath = dictCaseInsensitivePath.get(strCaseInsensitivePath)

        if strExistingPath is not None:
            raise ComponentManagementError(
                code="component_source_invalid",
                message="Component package contains paths that conflict on Windows.",
                details={"paths": [strExistingPath, strArchivePath]},
            )

        dictCaseInsensitivePath[strCaseInsensitivePath] = strArchivePath

        try:
            dictEntry[strArchivePath] = pathSource.read_bytes()
        except OSError as e:
            raise ComponentManagementError(
                code="io_error",
                message=f"Failed to read Component package file: {pathSource}",
            ) from e

    return dictEntry


def _validate_archive_path(archivePath: str) -> None:
    if archivePath == "" or archivePath.endswith("/"):
        raise ValueError(f"Wheel contains an invalid file path: {archivePath!r}.")

    if "\\" in archivePath:
        raise ValueError(f"Wheel path must use '/' separators: {archivePath!r}.")

    if archivePath.startswith("/") or _REGEX_WINDOWS_DRIVE_PATH.match(archivePath):
        raise ValueError(f"Wheel path must be relative: {archivePath!r}.")

    pathObj = PurePosixPath(archivePath)
    if any(part in {"", ".", ".."} for part in pathObj.parts):
        raise ValueError(f"Wheel contains an unsafe path: {archivePath!r}.")


def _read_metadata(value: bytes, _fileName: str) -> Message:
    return BytesParser(policy=policy.default).parsebytes(value)


def _validate_record(
    wheelObj: ZipFile,
    archivePathSet: set[str],
    recordPath: str,
) -> None:
    try:
        strRecord = wheelObj.read(recordPath).decode("utf-8", errors="strict")
    except (KeyError, UnicodeDecodeError) as e:
        raise ValueError("Wheel RECORD is missing or is not valid UTF-8.") from e

    listRow = list(reader(StringIO(strRecord, newline="")))
    dictRecordRow: dict[str, tuple[str, str]] = {}

    for row in listRow:
        if len(row) != 3:
            raise ValueError("Every Wheel RECORD row must contain exactly three fields.")

        strPath, strHash, strSize = row
        if strPath in dictRecordRow:
            raise ValueError(f"Wheel RECORD contains a duplicate path: {strPath!r}.")

        dictRecordRow[strPath] = (strHash, strSize)

    if set(dictRecordRow) != archivePathSet:
        listMissingPath = sorted(archivePathSet - set(dictRecordRow))
        listUnknownPath = sorted(set(dictRecordRow) - archivePathSet)
        raise ValueError(
            "Wheel RECORD paths do not match the Wheel contents. "
            f"Missing: {listMissingPath}; unknown: {listUnknownPath}."
        )

    for strPath in sorted(archivePathSet):
        strHash, strSize = dictRecordRow[strPath]

        if strPath == recordPath:
            if strHash != "" or strSize != "":
                raise ValueError("The Wheel RECORD row for RECORD itself must have empty hash and size fields.")
            continue

        value = wheelObj.read(strPath)
        if strHash != calculate_record_hash(value):
            raise ValueError(f"Wheel RECORD hash does not match: {strPath!r}.")

        if strSize != str(len(value)):
            raise ValueError(f"Wheel RECORD size does not match: {strPath!r}.")


def validate_component_wheel(
    wheelPath: Path,
    manifestObj: ComponentManifest,
    snippetCatalogDict: DictSnippetCatalogFile,
) -> str:
    dictPublishedManifest = _get_manifest_dict(manifestObj)
    strDistInfoFolder, strExpectedWheelFile = _get_wheel_names(manifestObj)

    if wheelPath.name != strExpectedWheelFile:
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message="Component Wheel filename does not match its Component metadata.",
            details={"wheelFile": wheelPath.name, "expectedWheelFile": strExpectedWheelFile},
        )

    try:
        normalizedName, versionObj, buildTag, tagSet = parse_wheel_filename(wheelPath.name)
        if normalizedName != canonicalize_name(manifestObj.packageName):
            raise ValueError("Wheel distribution name does not match packageName.")
        if versionObj != Version(manifestObj.version):
            raise ValueError("Wheel version does not match component.json.")
        if buildTag:
            raise ValueError("LiberRPA Component Wheels cannot use a build tag.")
        if tagSet != frozenset({Tag("py313", "none", "any")}):
            raise ValueError(f"Wheel must use the {_STR_WHEEL_TAG} compatibility tag.")

        with ZipFile(wheelPath, mode="r") as wheelObj:
            strBadFile = wheelObj.testzip()
            if strBadFile is not None:
                raise ValueError(f"Wheel ZIP integrity check failed: {strBadFile!r}.")

            listInfo = wheelObj.infolist()
            listArchivePath = [infoObj.filename for infoObj in listInfo]
            setArchivePath = set(listArchivePath)

            if len(setArchivePath) != len(listArchivePath):
                raise ValueError("Wheel contains duplicate paths.")

            dictCaseInsensitivePath: dict[str, str] = {}
            for infoObj in listInfo:
                strArchivePath = infoObj.filename
                _validate_archive_path(strArchivePath)

                intFileType = stat.S_IFMT(infoObj.external_attr >> 16)
                if intFileType == stat.S_IFLNK:
                    raise ValueError(f"Wheel cannot contain symbolic links: {strArchivePath!r}.")

                strCaseInsensitivePath = strArchivePath.casefold()
                strExistingPath = dictCaseInsensitivePath.get(strCaseInsensitivePath)
                if strExistingPath is not None:
                    raise ValueError(
                        f"Wheel contains paths that conflict on Windows: {strExistingPath!r}, {strArchivePath!r}."
                    )
                dictCaseInsensitivePath[strCaseInsensitivePath] = strArchivePath

                pathObj = PurePosixPath(strArchivePath)
                if pathObj.parts[0] not in {manifestObj.packageName, strDistInfoFolder}:
                    raise ValueError(f"Wheel contains an unexpected top-level path: {strArchivePath!r}.")

                if pathObj.parts[0] == manifestObj.packageName:
                    if "__pycache__" in pathObj.parts:
                        raise ValueError(f"Wheel cannot contain __pycache__: {strArchivePath!r}.")
                    if pathObj.suffix.casefold() in _SET_FORBIDDEN_FILE_SUFFIX:
                        raise ValueError(f"Wheel contains an unsupported file type: {strArchivePath!r}.")

            strMetadataPath = f"{strDistInfoFolder}/METADATA"
            strWheelMetadataPath = f"{strDistInfoFolder}/WHEEL"
            strLicensePath = f"{strDistInfoFolder}/licenses/LICENSE"
            strManifestPath = f"{strDistInfoFolder}/liberrpa/component.json"
            strCatalogPath = f"{strDistInfoFolder}/liberrpa/snippets_catalog.json"
            strRecordPath = f"{strDistInfoFolder}/RECORD"

            setRequiredPath = {
                f"{manifestObj.packageName}/__init__.py",
                f"{manifestObj.packageName}/py.typed",
                strMetadataPath,
                strWheelMetadataPath,
                strLicensePath,
                strManifestPath,
                strCatalogPath,
                strRecordPath,
            }
            listMissingPath = sorted(setRequiredPath - setArchivePath)
            if listMissingPath:
                raise ValueError(f"Wheel is missing required files: {listMissingPath}.")

            metadataObj = _read_metadata(wheelObj.read(strMetadataPath), "METADATA")
            if metadataObj.get("Metadata-Version") != "2.4":
                raise ValueError("Wheel METADATA must use Metadata-Version 2.4.")
            if canonicalize_name(metadataObj.get("Name", "")) != canonicalize_name(manifestObj.packageName):
                raise ValueError("Wheel METADATA Name does not match packageName.")
            if Version(metadataObj.get("Version", "")) != Version(manifestObj.version):
                raise ValueError("Wheel METADATA Version does not match component.json.")
            if metadataObj.get_all("Requires-Dist"):
                raise ValueError("LiberRPA Component Wheels cannot contain Requires-Dist metadata.")
            if metadataObj.get_all("License-File") != ["licenses/LICENSE"]:
                raise ValueError("Wheel METADATA must declare licenses/LICENSE.")

            wheelMetadataObj = _read_metadata(wheelObj.read(strWheelMetadataPath), "WHEEL")
            if wheelMetadataObj.get("Wheel-Version") != "1.0":
                raise ValueError("Wheel-Version must be 1.0.")
            if wheelMetadataObj.get("Root-Is-Purelib", "").casefold() != "true":
                raise ValueError("Root-Is-Purelib must be true.")
            if wheelMetadataObj.get_all("Tag") != [_STR_WHEEL_TAG]:
                raise ValueError(f"WHEEL must contain exactly one Tag: {_STR_WHEEL_TAG}.")

            embeddedManifest = parse_json(wheelObj.read(strManifestPath).decode("utf-8", errors="strict"))
            if embeddedManifest != dictPublishedManifest:
                raise ValueError("Embedded component.json does not match the published Component Manifest.")

            embeddedCatalog = parse_json(wheelObj.read(strCatalogPath).decode("utf-8", errors="strict"))
            if embeddedCatalog != snippetCatalogDict:
                raise ValueError("Embedded snippets_catalog.json does not match the generated catalog.")

            _validate_record(
                wheelObj=wheelObj,
                archivePathSet=setArchivePath,
                recordPath=strRecordPath,
            )
    except (BadZipFile, KeyError, OSError, UnicodeDecodeError, ValueError) as e:
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message=f"Built Component Wheel is invalid: {wheelPath}",
            details={"reason": str(e)},
        ) from e

    return calculate_file_sha256(wheelPath)


def _get_manifest_metadata_bytes(manifestObj: ComponentManifest) -> bytes:
    strMetadata = (
        # Core Metadata 2.4 is required because License-File was introduced in 2.4.
        "Metadata-Version: 2.4\n"
        f"Name: {manifestObj.packageName}\n"
        f"Version: {manifestObj.version}\n"
        "License-File: licenses/LICENSE\n"
        "\n"
    )
    return strMetadata.encode("utf-8")


def _get_wheel_metadata_bytes() -> bytes:
    return (
        # LiberRPA Component Wheels currently follow Wheel specification 1.0.
        f"Wheel-Version: 1.0\nGenerator: LiberRPA ComponentManagement\nRoot-Is-Purelib: true\nTag: {_STR_WHEEL_TAG}\n\n"
    ).encode()


def _get_record_bytes(
    archiveEntryDict: dict[str, bytes],
    recordPath: str,
) -> bytes:
    strBuffer = StringIO(newline="")
    csvWriter = writer(strBuffer, lineterminator="\n")

    for strArchivePath in sorted(archiveEntryDict):
        value = archiveEntryDict[strArchivePath]
        csvWriter.writerow([
            strArchivePath,
            calculate_record_hash(value),
            str(len(value)),
        ])

    csvWriter.writerow([recordPath, "", ""])
    return strBuffer.getvalue().encode("utf-8")


def _create_zip_info(archivePath: str) -> ZipInfo:
    infoObj = ZipInfo(filename=archivePath, date_time=_TUPLE_ZIP_TIMESTAMP)
    infoObj.compress_type = ZIP_STORED
    infoObj.create_system = 3
    infoObj.external_attr = _INT_ZIP_FILE_MODE
    return infoObj


def _write_wheel_file(
    wheelPath: Path,
    archiveEntryDict: dict[str, bytes],
    recordPath: str,
) -> None:
    pathTemp = wheelPath.parent / f".{wheelPath.name}.{uuid.uuid4()}.tmp"

    try:
        with ZipFile(pathTemp, mode="x", compression=ZIP_STORED) as wheelObj:
            for strArchivePath in sorted(archiveEntryDict):
                wheelObj.writestr(
                    _create_zip_info(strArchivePath),
                    archiveEntryDict[strArchivePath],
                )

            wheelObj.writestr(
                _create_zip_info(recordPath),
                _get_record_bytes(archiveEntryDict=archiveEntryDict, recordPath=recordPath),
            )

        os.replace(pathTemp, wheelPath)
    except (OSError, BadZipFile) as e:
        raise ComponentManagementError(
            code="wheel_build_failed",
            message=f"Failed to build Component Wheel: {wheelPath}",
        ) from e
    finally:
        pathTemp.unlink(missing_ok=True)


def build_component_wheel(
    projectPath: Path,
    packagePath: Path,
    manifestObj: ComponentManifest,
    snippetCatalog: DictSnippetCatalogFile,
) -> WheelBuildResult:
    licensePath = projectPath / "LICENSE"
    if not licensePath.is_file() or licensePath.is_symlink():
        raise ComponentManagementError(
            code="component_source_invalid",
            message=f"Component Project LICENSE file was not found or is invalid: {licensePath}",
        )

    strDistInfoFolder, strWheelFile = _get_wheel_names(manifestObj)
    pathBuildFolder = projectPath / ".liberrpa-project-manager" / "build"
    pathWheel = pathBuildFolder / strWheelFile

    try:
        licenseValue = licensePath.read_bytes()
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to read Component Project LICENSE file: {licensePath}",
        ) from e

    dictArchiveEntry = _get_package_archive_entries(
        packagePath=packagePath,
        packageName=manifestObj.packageName,
    )

    dictPublishedManifest = _get_manifest_dict(manifestObj)
    strDistInfoPrefix = f"{strDistInfoFolder}/"
    dictArchiveEntry.update({
        f"{strDistInfoPrefix}METADATA": _get_manifest_metadata_bytes(manifestObj),
        f"{strDistInfoPrefix}WHEEL": _get_wheel_metadata_bytes(),
        f"{strDistInfoPrefix}licenses/LICENSE": licenseValue,
        f"{strDistInfoPrefix}liberrpa/component.json": serialize_json(dictPublishedManifest).encode("utf-8"),
        f"{strDistInfoPrefix}liberrpa/snippets_catalog.json": serialize_json(snippetCatalog).encode("utf-8"),
    })

    strRecordPath = f"{strDistInfoPrefix}RECORD"

    try:
        pathBuildFolder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to create Component build folder: {pathBuildFolder}",
        ) from e

    _write_wheel_file(
        wheelPath=pathWheel,
        archiveEntryDict=dictArchiveEntry,
        recordPath=strRecordPath,
    )
    strSha256 = validate_component_wheel(
        wheelPath=pathWheel,
        manifestObj=manifestObj,
        snippetCatalogDict=snippetCatalog,
    )

    return WheelBuildResult(
        wheelPath=pathWheel,
        wheelFile=strWheelFile,
        sha256=strSha256,
    )
