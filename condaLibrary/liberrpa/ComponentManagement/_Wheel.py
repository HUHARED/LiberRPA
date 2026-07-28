# FileName: _Wheel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import parse_json, serialize_json
from liberrpa.ComponentManagement.Utils._Hash import calculate_file_sha256, calculate_record_hash
from liberrpa.ComponentManagement.Utils._TypedValue import (
    ComponentManifest,
    DictSnippetImports,
    DictNormalizedSnippet,
    DictSnippetCatalogFile,
    WheelBuildResult,
    ComponentWheelInfo,
)
from liberrpa.ComponentManagement.Utils._Validation import validate_exact_keys
from liberrpa.ComponentManagement._Manifest import parse_component_manifest

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
    ZIP_STORED,  # Avoid compressor-version differences so identical inputs produce identical Wheel bytes and SHA-256 values.
    BadZipFile,
    ZipFile,
    ZipInfo,
)
import keyword
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

# LiberRPA runs only on Windows, so Component packages may include user-managed script resources such as .bat, .cmd, and .ps1 files. Native libraries, Python extension modules, and standalone executable binaries remain unsupported to keep Component packaging and recovery predictable.
_SET_FORBIDDEN_FILE_SUFFIX = {
    # ".bat",
    # ".cmd",
    # ".ps1",
    ".dll",
    ".dylib",
    ".exe",
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


def _get_manifest_metadata_bytes(manifestObj: ComponentManifest) -> bytes:
    strMetadata = (
        # Core Metadata 2.4 is required because License-File was introduced in 2.4.
        "Metadata-Version: 2.4\n"
        f"Name: {manifestObj.packageName}\n"
        f"Version: {manifestObj.version}\n"
        # License-File: LICENSE == <dist-info>/licenses/LICENSE
        "License-File: LICENSE\n"
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
    buildFolderPath: Path,
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
    pathWheel = buildFolderPath / strWheelFile

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
        f"{strDistInfoPrefix}component.json": serialize_json(dictPublishedManifest).encode("utf-8"),
        f"{strDistInfoPrefix}snippets_catalog.json": serialize_json(snippetCatalog).encode("utf-8"),
    })

    strRecordPath = f"{strDistInfoPrefix}RECORD"

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


def _validate_archive_path(archivePath: str) -> None:
    if archivePath == "" or archivePath.endswith("/"):
        raise ValueError(f"Wheel contains an invalid file path: {archivePath!r}.")

    if "\x00" in archivePath:
        raise ValueError(f"Wheel path contains a null character: {archivePath!r}.")

    if "\\" in archivePath:
        raise ValueError(f"Wheel path must use '/' separators: {archivePath!r}.")

    if archivePath.startswith("/") or _REGEX_WINDOWS_DRIVE_PATH.match(archivePath):
        raise ValueError(f"Wheel path must be relative: {archivePath!r}.")

    listPathPart = archivePath.split("/")

    if any(pathPart in {"", ".", ".."} for pathPart in listPathPart):
        raise ValueError(f"Wheel contains an unsafe path: {archivePath!r}.")


def _read_metadata(value: bytes, fileName: str) -> Message:
    metadataObj = BytesParser(
        policy=policy.compat32,
    ).parsebytes(
        value,
        headersonly=True,
    )

    if metadataObj.defects:
        raise ValueError(f"Invalid metadata headers in {fileName}: {metadataObj.defects!r}.")

    return metadataObj


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


_SET_SNIPPET_CATALOG_KEYS = {
    "schemaVersion",
    "categoryOrder",
    "importSources",
    "snippets",
}
_SET_IMPORT_SOURCE_CONFIG_KEYS = {"order", "aliasMode"}
_SET_NORMALIZED_SNIPPET_KEYS = {
    "category",
    "label",
    "prefix",
    "body",
    "description",
    "imports",
    "insertionMode",
}


def _validate_identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.isidentifier() or keyword.iskeyword(value):
        raise ValueError(f"{field} must be a valid non-keyword Python identifier.")

    return value


def _validate_single_line_string(value: object, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field} must be a non-empty string.")

    if "\r" in value or "\n" in value:
        raise ValueError(f"{field} must be a single line.")

    return value


def _validate_catalog_imports(
    value: object,
    field: str,
    *,
    packageName: str,
    publicModuleSet: set[str],
) -> DictSnippetImports:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    dictResult: DictSnippetImports = {}

    for importSource, importNameValue in value.items():
        if not isinstance(importSource, str) or importSource == "":
            raise ValueError(f"{field} contains an invalid import source.")

        if not isinstance(importNameValue, list) or not importNameValue:
            raise ValueError(f"{field}.{importSource} must be a non-empty array.")

        listImportName: list[str] = []
        setImportName: set[str] = set()

        for intIndex, importName in enumerate(importNameValue):
            strImportName = _validate_identifier(
                importName,
                f"{field}.{importSource}[{intIndex}]",
            )

            if strImportName in setImportName:
                raise ValueError(f"{field}.{importSource} contains duplicate import name {strImportName!r}.")

            if importSource == packageName and strImportName not in publicModuleSet:
                raise ValueError(f"{field}.{importSource} contains unknown public Module {strImportName!r}.")

            setImportName.add(strImportName)
            listImportName.append(strImportName)

        dictResult[importSource] = listImportName

    return dictResult


def _validate_snippet_catalog(
    value: object,
    manifestObj: ComponentManifest,
) -> DictSnippetCatalogFile:
    if not isinstance(value, dict):
        raise ValueError("snippets_catalog.json root value must be an object.")

    validate_exact_keys(value, _SET_SNIPPET_CATALOG_KEYS, "snippets_catalog.json")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("snippets_catalog.json schemaVersion must be 1.")

    importSourcesValue = value.get("importSources")
    if not isinstance(importSourcesValue, dict):
        raise ValueError("snippets_catalog.json importSources must be an object.")

    if set(importSourcesValue) != {manifestObj.packageName}:
        raise ValueError("A Component snippets catalog must define exactly its own packageName as the import source.")

    sourceConfigValue = importSourcesValue[manifestObj.packageName]
    if not isinstance(sourceConfigValue, dict):
        raise ValueError(f"importSources.{manifestObj.packageName} must be an object.")

    validate_exact_keys(
        sourceConfigValue,
        _SET_IMPORT_SOURCE_CONFIG_KEYS,
        f"importSources.{manifestObj.packageName}",
    )

    if sourceConfigValue.get("aliasMode") != "source_module":
        raise ValueError(f"importSources.{manifestObj.packageName}.aliasMode must be 'source_module'.")

    moduleOrderValue = sourceConfigValue.get("order")
    if not isinstance(moduleOrderValue, list):
        raise ValueError(f"importSources.{manifestObj.packageName}.order must be an array.")

    listModuleOrder: list[str] = []
    setModule: set[str] = set()

    for intIndex, moduleName in enumerate(moduleOrderValue):
        strModuleName = _validate_identifier(
            moduleName,
            f"importSources.{manifestObj.packageName}.order[{intIndex}]",
        )
        if strModuleName in setModule:
            raise ValueError(
                f"importSources.{manifestObj.packageName}.order contains duplicate Module {strModuleName!r}."
            )
        setModule.add(strModuleName)
        listModuleOrder.append(strModuleName)

    categoryOrderValue = value.get("categoryOrder")
    if not isinstance(categoryOrderValue, list):
        raise ValueError("snippets_catalog.json categoryOrder must be an array.")

    listCategoryOrder: list[str] = []
    setCategory: set[str] = set()
    strCategoryPrefix = f"{manifestObj.packageName}_"

    for intIndex, category in enumerate(categoryOrderValue):
        if not isinstance(category, str) or not category.startswith(strCategoryPrefix):
            raise ValueError(f"categoryOrder[{intIndex}] must use {manifestObj.packageName}_ModuleName.")

        strModuleName = category[len(strCategoryPrefix) :]
        if strModuleName not in setModule:
            raise ValueError(f"categoryOrder[{intIndex}] refers to an unknown public Module.")

        if category in setCategory:
            raise ValueError(f"categoryOrder contains duplicate category {category!r}.")

        setCategory.add(category)
        listCategoryOrder.append(category)

    snippetsValue = value.get("snippets")
    if not isinstance(snippetsValue, dict):
        raise ValueError("snippets_catalog.json snippets must be an object.")

    dictSnippet: dict[str, DictNormalizedSnippet] = {}
    setUsedCategory: set[str] = set()
    dictLabelOwner: dict[tuple[str, str], str] = {}
    dictPrefixOwner: dict[str, str] = {}

    for snippetKey, snippetValue in snippetsValue.items():
        if not isinstance(snippetKey, str):
            raise ValueError("Every Snippet key must be a string.")

        strCategory, strSeparator, strSnippetName = snippetKey.partition(".")
        if (
            strSeparator == ""
            or "." in strSnippetName
            or strCategory not in setCategory
            or not strSnippetName.isidentifier()
            or keyword.iskeyword(strSnippetName)
        ):
            raise ValueError(f"Invalid Component Snippet key: {snippetKey!r}.")

        if not isinstance(snippetValue, dict):
            raise ValueError(f"snippets.{snippetKey} must be an object.")

        validate_exact_keys(
            snippetValue,
            _SET_NORMALIZED_SNIPPET_KEYS,
            f"snippets.{snippetKey}",
        )

        if snippetValue.get("category") != strCategory:
            raise ValueError(f"snippets.{snippetKey}.category does not match its key.")

        strLabel = _validate_single_line_string(
            snippetValue.get("label"),
            f"snippets.{snippetKey}.label",
        )
        strPrefix = _validate_single_line_string(
            snippetValue.get("prefix"),
            f"snippets.{snippetKey}.prefix",
        )

        bodyValue = snippetValue.get("body")
        if (
            not isinstance(bodyValue, list)
            or not bodyValue
            or not all(isinstance(line, str) for line in bodyValue)
            or all(line.strip() == "" for line in bodyValue)
        ):
            raise ValueError(f"snippets.{snippetKey}.body must be a non-empty array of strings.")
        listBody = list(bodyValue)

        description = snippetValue.get("description")
        if not isinstance(description, str) or description.strip() == "":
            raise ValueError(f"snippets.{snippetKey}.description must be a non-empty string.")

        insertionMode = snippetValue.get("insertionMode")
        if insertionMode not in {"line", "cursor"}:
            raise ValueError(f"snippets.{snippetKey}.insertionMode must be 'line' or 'cursor'.")

        dictImports = _validate_catalog_imports(
            snippetValue.get("imports"),
            f"snippets.{snippetKey}.imports",
            packageName=manifestObj.packageName,
            publicModuleSet=setModule,
        )

        strModuleName = strCategory[len(strCategoryPrefix) :]
        if strModuleName not in dictImports.get(manifestObj.packageName, []):
            raise ValueError(f"snippets.{snippetKey}.imports must include its own public Module {strModuleName!r}.")

        tupleLabel = (strCategory, strLabel)
        strExistingLabelOwner = dictLabelOwner.get(tupleLabel)
        if strExistingLabelOwner is not None:
            raise ValueError(
                f"snippets.{snippetKey}.label duplicates {strExistingLabelOwner!r} within category {strCategory!r}."
            )
        dictLabelOwner[tupleLabel] = snippetKey

        strExistingPrefixOwner = dictPrefixOwner.get(strPrefix)
        if strExistingPrefixOwner is not None:
            raise ValueError(f"snippets.{snippetKey}.prefix duplicates {strExistingPrefixOwner!r}.")
        dictPrefixOwner[strPrefix] = snippetKey

        setUsedCategory.add(strCategory)
        dictSnippet[snippetKey] = {
            "category": strCategory,
            "label": strLabel,
            "prefix": strPrefix,
            "body": listBody,
            "description": description,
            "imports": dictImports,
            "insertionMode": insertionMode,
        }

    if setCategory != setUsedCategory:
        raise ValueError("categoryOrder must contain exactly the categories used by the final Snippets.")

    listExpectedCategoryOrder = [
        f"{manifestObj.packageName}_{moduleName}"
        for moduleName in listModuleOrder
        if f"{manifestObj.packageName}_{moduleName}" in setUsedCategory
    ]
    if listCategoryOrder != listExpectedCategoryOrder:
        raise ValueError("categoryOrder must follow the Component import source Module order.")

    return {
        "schemaVersion": 1,
        "categoryOrder": listCategoryOrder,
        "importSources": {
            manifestObj.packageName: {
                "order": listModuleOrder,
                "aliasMode": "source_module",
            }
        },
        "snippets": dictSnippet,
    }


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
            details={
                "wheelFile": wheelPath.name,
                "expectedWheelFile": strExpectedWheelFile,
            },
        )

    try:
        dictExpectedSnippetCatalog = _validate_snippet_catalog(snippetCatalogDict, manifestObj)

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

            strMetadataPath = f"{strDistInfoFolder}/METADATA"
            strWheelMetadataPath = f"{strDistInfoFolder}/WHEEL"
            strLicensePath = f"{strDistInfoFolder}/licenses/LICENSE"
            strManifestPath = f"{strDistInfoFolder}/component.json"
            strCatalogPath = f"{strDistInfoFolder}/snippets_catalog.json"
            strRecordPath = f"{strDistInfoFolder}/RECORD"

            listInfo = wheelObj.infolist()
            listArchivePath = [infoObj.filename for infoObj in listInfo]
            setArchivePath = set(listArchivePath)

            if len(setArchivePath) != len(listArchivePath):
                raise ValueError("Wheel contains duplicate paths.")

            dictCaseInsensitivePath: dict[str, str] = {}
            for infoObj in listInfo:
                strArchivePath = infoObj.filename
                _validate_archive_path(strArchivePath)

                if infoObj.compress_type != ZIP_STORED:
                    raise ValueError(f"Wheel file must use ZIP_STORED compression: {strArchivePath!r}.")
                if infoObj.date_time != _TUPLE_ZIP_TIMESTAMP:
                    raise ValueError(f"Wheel file has a non-deterministic timestamp: {strArchivePath!r}.")
                if infoObj.create_system != 3 or infoObj.external_attr != _INT_ZIP_FILE_MODE:
                    raise ValueError(f"Wheel file has invalid permission metadata: {strArchivePath!r}.")

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
                    if pathObj.suffix.casefold() in _SET_IGNORED_FILE_SUFFIX:
                        raise ValueError(f"Wheel cannot contain ignored Python cache files: {strArchivePath!r}.")
                    if pathObj.suffix.casefold() in _SET_FORBIDDEN_FILE_SUFFIX:
                        raise ValueError(f"Wheel contains an unsupported file type: {strArchivePath!r}.")

            setExpectedDistInfoPath = {
                strMetadataPath,
                strWheelMetadataPath,
                strLicensePath,
                strManifestPath,
                strCatalogPath,
                strRecordPath,
            }
            setRequiredPath = {
                f"{manifestObj.packageName}/__init__.py",
                f"{manifestObj.packageName}/py.typed",
                *setExpectedDistInfoPath,
            }
            listMissingPath = sorted(setRequiredPath - setArchivePath)
            if listMissingPath:
                raise ValueError(f"Wheel is missing required files: {listMissingPath}.")

            setActualDistInfoPath = {
                strArchivePath
                for strArchivePath in setArchivePath
                if PurePosixPath(strArchivePath).parts[0] == strDistInfoFolder
            }
            if setActualDistInfoPath != setExpectedDistInfoPath:
                raise ValueError(
                    "Wheel .dist-info files do not match the LiberRPA Component Wheel structure. "
                    f"Unexpected: {sorted(setActualDistInfoPath - setExpectedDistInfoPath)}."
                )

            listExpectedArchivePath = [
                *sorted(setArchivePath - {strRecordPath}),
                strRecordPath,
            ]
            if listArchivePath != listExpectedArchivePath:
                raise ValueError("Wheel files are not stored in the deterministic LiberRPA order.")

            metadataObj = _read_metadata(wheelObj.read(strMetadataPath), "METADATA")
            if metadataObj.get("Metadata-Version") != "2.4":
                raise ValueError("Wheel METADATA must use Metadata-Version 2.4.")
            if canonicalize_name(metadataObj.get("Name", "")) != canonicalize_name(manifestObj.packageName):
                raise ValueError("Wheel METADATA Name does not match packageName.")
            if Version(metadataObj.get("Version", "")) != Version(manifestObj.version):
                raise ValueError("Wheel METADATA Version does not match component.json.")
            if metadataObj.get_all("Requires-Dist"):
                raise ValueError("LiberRPA Component Wheels cannot contain Requires-Dist metadata.")
            if metadataObj.get_all("License-File") != ["LICENSE"]:
                raise ValueError("Wheel METADATA must declare LICENSE.")

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
            dictEmbeddedSnippetCatalog = _validate_snippet_catalog(embeddedCatalog, manifestObj)
            if dictEmbeddedSnippetCatalog != dictExpectedSnippetCatalog:
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


def inspect_component_wheel(wheelPath: Path) -> ComponentWheelInfo:
    if not wheelPath.is_file() or wheelPath.is_symlink():
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message=f"Component Wheel file was not found or is invalid: {wheelPath}",
        )

    try:
        with ZipFile(wheelPath, mode="r") as wheelObj:
            listManifestPath = [
                infoObj.filename
                for infoObj in wheelObj.infolist()
                if PurePosixPath(infoObj.filename).name == "component.json"
                and PurePosixPath(infoObj.filename).parent.name.endswith(".dist-info")
            ]

            if len(listManifestPath) != 1:
                raise ValueError("Wheel must contain exactly one component.json directly inside its .dist-info folder.")

            strManifestPath = listManifestPath[0]
            pathDistInfo = PurePosixPath(strManifestPath).parent
            strCatalogPath = (pathDistInfo / "snippets_catalog.json").as_posix()

            embeddedManifest = parse_json(wheelObj.read(strManifestPath).decode("utf-8", errors="strict"))
            manifestObj = parse_component_manifest(
                embeddedManifest,
                sourceName=strManifestPath,
            )

            embeddedCatalog = parse_json(wheelObj.read(strCatalogPath).decode("utf-8", errors="strict"))
            dictSnippetCatalog = _validate_snippet_catalog(embeddedCatalog, manifestObj)
    except ComponentManagementError:
        raise
    except (BadZipFile, KeyError, OSError, UnicodeDecodeError, ValueError) as e:
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message=f"Component Wheel is invalid: {wheelPath}",
            details={"reason": str(e)},
        ) from e

    strSha256 = validate_component_wheel(
        wheelPath=wheelPath,
        manifestObj=manifestObj,
        snippetCatalogDict=dictSnippetCatalog,
    )

    return ComponentWheelInfo(
        manifest=manifestObj,
        snippetCatalog=dictSnippetCatalog,
        wheelFile=wheelPath.name,
        sha256=strSha256,
    )
